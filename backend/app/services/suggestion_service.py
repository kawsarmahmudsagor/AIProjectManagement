import logging
from datetime import UTC, datetime, timedelta
from typing import Literal
from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models.repo_suggestion import RepoSuggestion, SuggestionSource
from app.models.user import User
from app.services.github_cache_service import get_cached_repos
from app.services.portfolio_service import compute_technology_frequency

logger = logging.getLogger(__name__)

# Excluded from proactive suggestion generation ONLY (recompute_user_suggestions below) —
# never from compute_technology_frequency's own output, which agents/chat_tools.py's
# portfolio_analysis tool and this app's other analytics still need to report honestly,
# generic-stack entries included. The point here is narrower: a user's "top technologies"
# by raw project count skews toward whatever language/framework/DB they use on everything
# (Python, TypeScript, SQL...), crowding out the more specific, interesting technology a
# repo suggestion is actually useful for (an LLM framework, a RAG tool, a notable Unity/AR
# plugin, ...). Filtering happens before ranking, so a filtered-out entry never occupies
# one of the top-N slots in the first place — it isn't merely deprioritized.
#
# Free-text, single-token match against whatever a user typed into a project's
# `technologies` field — a project listing both "Unity" (generic, filtered) and, say,
# "AR Foundation" (specific, kept) still surfaces the latter. Not exhaustive; extend this
# set as more generic entries turn up in practice.
_GENERIC_TECHNOLOGIES: frozenset[str] = frozenset(
    {
        # Languages
        "python", "javascript", "typescript", "java", "c", "c++", "c#", "go", "golang",
        "rust", "ruby", "php", "swift", "kotlin", "scala", "dart", "html", "html5", "css",
        "css3", "sql", "bash", "shell", "powershell",
        # Core runtimes / broad platforms
        "node", "node.js", "nodejs", ".net", "dotnet", "jvm",
        # General-purpose web frameworks/libraries
        "react", "react.js", "vue", "vue.js", "angular", "next.js", "nextjs", "nuxt",
        "express", "express.js", "fastapi", "django", "flask", "spring", "spring boot",
        "asp.net", "jquery", "bootstrap", "tailwind", "tailwind css",
        # Databases / data-layer basics
        "sql alchemy", "sqlalchemy", "postgresql", "postgres", "mysql", "sqlite",
        "mongodb", "redis", "prisma",
        # Generic infra/tooling
        "docker", "kubernetes", "git", "github", "github actions", "npm", "pip", "yarn",
        "webpack", "vite", "jest", "pytest", "rest", "rest api", "api", "json", "xml",
        "yaml", "aws", "azure", "gcp", "linux", "windows", "macos",
        # Game-engine basics (kept generic only — a named plugin/toolkit still counts)
        "unity", "unreal", "unreal engine", "unity engine",
    }
)


def _is_suggestable_technology(name: str) -> bool:
    return name.strip().lower() not in _GENERIC_TECHNOLOGIES


async def get_suggested_repo_full_names(db: AsyncSession, user_id: UUID) -> set[str]:
    """Every repo full_name ever suggested to this user, via any technology or source
    (dashboard or chat) — the single no-repeat check both surfaces share."""
    rows = (
        await db.execute(select(RepoSuggestion.repo_full_name).where(RepoSuggestion.user_id == user_id))
    ).scalars().all()
    return set(rows)


async def record_chat_suggestions(db: AsyncSession, user_id: UUID, query: str, repos: list[dict]) -> None:
    """Logs repos the chat tool actually surfaced to the user so neither chat nor the
    dashboard ever offers them again. `repos` must already be filtered against
    get_suggested_repo_full_names — this doesn't re-check, only records."""
    if not repos:
        return
    settings = get_settings()
    now = datetime.now(UTC)
    expires_at = now + timedelta(hours=settings.github_suggestions_ttl_hours)
    technology_display = query[:40]
    key = technology_display.lower()
    for repo in repos:
        db.add(
            RepoSuggestion(
                user_id=user_id,
                technology=key,
                technology_display=technology_display,
                repo_full_name=repo["full_name"],
                repo=repo,
                source=SuggestionSource.CHAT,
                rank=0,
                computed_at=now,
                expires_at=expires_at,
            )
        )
    await db.commit()


async def recompute_user_suggestions(db: AsyncSession, user_id: UUID, *, force: bool = False) -> bool:
    """Recomputes this user's dashboard repo suggestions from their current top
    technologies. No-ops (returns False) if the toggle is off, or if suggestions were
    already computed within the debounce window and `force` isn't set. Returns True if a
    live GitHub call during this run got rate-limited, so the cron batch (below) can back
    off early."""
    settings = get_settings()
    user = await db.get(User, user_id)
    if user is None or not user.chatbot_preemptive_github_suggestions:
        return False

    if not force:
        last_computed = (
            await db.execute(
                select(func.max(RepoSuggestion.computed_at)).where(RepoSuggestion.user_id == user_id)
            )
        ).scalar_one_or_none()
        if last_computed is not None:
            cutoff = datetime.now(UTC) - timedelta(hours=settings.github_suggestions_debounce_hours)
            if last_computed > cutoff:
                return False

    freq = await compute_technology_frequency(db, user_id)
    suggestable = [t for t in freq["technologies"] if _is_suggestable_technology(t["name"])]
    top_technologies = suggestable[: settings.github_suggestions_top_technologies]
    top_keys = {t["name"].lower() for t in top_technologies}

    existing = (
        await db.execute(select(RepoSuggestion).where(RepoSuggestion.user_id == user_id))
    ).scalars().all()
    already_suggested = {r.repo_full_name for r in existing}
    existing_by_tech: dict[str, list[RepoSuggestion]] = {}
    for row in existing:
        existing_by_tech.setdefault(row.technology, []).append(row)

    now = datetime.now(UTC)
    expires_at = now + timedelta(hours=settings.github_suggestions_ttl_hours)
    rate_limited = False

    for tech in top_technologies:
        display_name = tech["name"]
        key = display_name.lower()
        tech_rows = existing_by_tech.get(key, [])

        # Touch existing rows so they don't go stale, without disturbing `dismissed` —
        # dismissing a repo is durable across recomputes even if it's still GitHub's top
        # pick for this technology.
        for i, row in enumerate(tech_rows):
            row.computed_at = now
            row.expires_at = expires_at
            row.rank = i

        # Cap total suggestions ever made per (user, technology) rather than growing it
        # every recompute — a dismissed slot doesn't reopen; this technology is simply
        # "done" once it's had its allotment.
        slots_open = settings.github_suggestions_repos_per_technology - len(tech_rows)
        if slots_open <= 0:
            continue

        cache_result = await get_cached_repos(db, display_name, limit=10)
        if cache_result.get("rate_limited"):
            rate_limited = True
        candidates = [
            repo for repo in cache_result.get("repos", []) if repo["full_name"] not in already_suggested
        ]
        for i, repo in enumerate(candidates[:slots_open]):
            db.add(
                RepoSuggestion(
                    user_id=user_id,
                    technology=key,
                    technology_display=display_name,
                    repo_full_name=repo["full_name"],
                    repo=repo,
                    source=SuggestionSource.DASHBOARD,
                    rank=len(tech_rows) + i,
                    computed_at=now,
                    expires_at=expires_at,
                )
            )
            already_suggested.add(repo["full_name"])

    # Technologies that fell out of the current top-N entirely are dropped, including any
    # dismissed rows — nothing will ever regenerate them again.
    for key, rows in existing_by_tech.items():
        if key not in top_keys:
            for row in rows:
                await db.delete(row)

    await db.commit()
    return rate_limited


async def list_suggestions(
    db: AsyncSession, user_id: UUID, *, scope: Literal["recent", "all"] = "recent"
) -> list[RepoSuggestion]:
    """`scope="recent"` (the Dashboard card): active (never-dismissed) suggestions from
    within the last `github_suggestions_dashboard_window_hours` — this is what stops the
    card from accumulating every suggestion ever computed. `scope="all"` (the Conversations
    page's Suggestions section): the complete history for this user, dismissed or not, most
    recent first — dismissing there (or on the Dashboard) is the same durable
    RepoSuggestion.dismissed flag either way, so a dismissal made on one page is reflected
    on the other the next time it's loaded."""
    stmt = select(RepoSuggestion).where(RepoSuggestion.user_id == user_id)
    if scope == "recent":
        settings = get_settings()
        window_start = datetime.now(UTC) - timedelta(hours=settings.github_suggestions_dashboard_window_hours)
        stmt = stmt.where(
            RepoSuggestion.dismissed.is_(False), RepoSuggestion.computed_at >= window_start
        ).order_by(RepoSuggestion.technology, RepoSuggestion.rank)
    else:
        stmt = stmt.order_by(RepoSuggestion.computed_at.desc())
    rows = (await db.execute(stmt)).scalars().all()
    return list(rows)


async def dismiss_suggestion(db: AsyncSession, user_id: UUID, suggestion_id: UUID) -> RepoSuggestion | None:
    row = (
        await db.execute(
            select(RepoSuggestion).where(
                RepoSuggestion.id == suggestion_id, RepoSuggestion.user_id == user_id
            )
        )
    ).scalar_one_or_none()
    if row is None:
        return None
    row.dismissed = True
    row.dismissed_at = datetime.now(UTC)
    await db.commit()
    await db.refresh(row)
    return row


async def find_stale_user_ids(db: AsyncSession, *, limit: int) -> list[UUID]:
    """Users with preemptive suggestions on, whose suggestions are missing or older than
    the staleness TTL — oldest-stale (or never-computed) first, capped at `limit` for the
    cron job's batching."""
    settings = get_settings()
    cutoff = datetime.now(UTC) - timedelta(hours=settings.github_suggestions_ttl_hours)
    last_computed = (
        select(
            RepoSuggestion.user_id.label("user_id"),
            func.max(RepoSuggestion.computed_at).label("last_computed_at"),
        )
        .group_by(RepoSuggestion.user_id)
        .subquery()
    )
    stmt = (
        select(User.id)
        .outerjoin(last_computed, last_computed.c.user_id == User.id)
        .where(
            User.chatbot_preemptive_github_suggestions.is_(True),
            or_(last_computed.c.last_computed_at.is_(None), last_computed.c.last_computed_at < cutoff),
        )
        .order_by(last_computed.c.last_computed_at.asc().nulls_first())
        .limit(limit)
    )
    return list((await db.execute(stmt)).scalars().all())


async def recompute_stale_suggestions(db: AsyncSession) -> None:
    """Cron entry point (app/workers/suggestion_refresh.py). Per-user errors are caught so
    one user's GitHub failure doesn't abort the batch; the batch stops early on an actual
    rate-limit response — the remaining stale users simply stay stale and are retried on
    the next tick, which is a natural backoff."""
    settings = get_settings()
    user_ids = await find_stale_user_ids(db, limit=settings.github_suggestions_cron_batch_size)
    for user_id in user_ids:
        try:
            rate_limited = await recompute_user_suggestions(db, user_id, force=True)
        except Exception:
            # One user's GitHub/DB failure shouldn't abort the rest of the batch.
            logger.exception("Failed to recompute suggestions for user %s", user_id)
            continue
        if rate_limited:
            break
