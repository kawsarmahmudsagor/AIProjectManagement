import asyncio
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models.github_repo_cache import GithubRepoCache
from app.services.github_service import search_github_repos

# Cross-user cache to keep the background suggestion job (which fans out across many
# users' overlapping technologies) far under GitHub's shared rate limit — see
# app/services/suggestion_service.py. Live chat search (chat_tools.github_search) stays
# uncached and calls search_github_repos directly: it's low-volume/human-paced, and its
# docstring promises "real, current" results.

_last_call_at: datetime | None = None
_pace_lock = asyncio.Lock()


async def _wait_for_rate_limit_slot() -> None:
    """In-process pacing for real (cache-miss) outbound GitHub calls made by the
    background suggestion job. Scoped to this process only — the FastAPI process and the
    SAQ worker process are separate OS processes, so this can't see the other's traffic.
    That's an accepted tradeoff: the cron/event-driven recompute path is the dominant,
    bursty consumer and runs entirely inside the worker process, while live chat traffic
    is low-volume; a shared cross-process limiter would need a Postgres-locked counter
    row, which isn't justified unless rate-limit errors are observed in practice."""
    global _last_call_at
    settings = get_settings()
    async with _pace_lock:
        if _last_call_at is not None:
            elapsed = (datetime.now(UTC) - _last_call_at).total_seconds()
            wait = settings.github_suggestions_min_call_interval_seconds - elapsed
            if wait > 0:
                await asyncio.sleep(wait)
        _last_call_at = datetime.now(UTC)


async def get_cached_repos(db: AsyncSession, technology: str, *, limit: int) -> dict:
    """Returns {"repos": [...]}, preferring a fresh cache row for this technology. On a
    cache miss (or expired row), paces and makes a live call, caching the result — a
    larger fetch than `limit` (min 10) so recompute has headroom to skip already-suggested
    repos without a second API call. Falls back to a stale cache row rather than an empty
    result if the live call errors."""
    settings = get_settings()
    key = technology.lower()
    now = datetime.now(UTC)

    row = (
        await db.execute(select(GithubRepoCache).where(GithubRepoCache.technology == key))
    ).scalar_one_or_none()

    if row is not None and row.expires_at > now:
        return {"repos": row.repos[:limit]}

    await _wait_for_rate_limit_slot()
    fetch_limit = max(limit, 10)
    result = await search_github_repos(technology, limit=fetch_limit)

    if result.get("error") or not result.get("repos"):
        if row is not None:
            # Stale-but-real beats empty — surface last-known-good repos while the live
            # call is failing. Still propagate rate_limited so the caller can back off
            # making further live calls this batch, even though this one had a fallback.
            return {"repos": row.repos[:limit], "rate_limited": result.get("rate_limited", False)}
        return {"repos": [], "error": result.get("error"), "rate_limited": result.get("rate_limited", False)}

    expires_at = now + timedelta(hours=settings.github_suggestion_cache_ttl_hours)
    if row is None:
        db.add(GithubRepoCache(technology=key, repos=result["repos"], fetched_at=now, expires_at=expires_at))
    else:
        row.repos = result["repos"]
        row.fetched_at = now
        row.expires_at = expires_at
    await db.commit()

    return {"repos": result["repos"][:limit]}
