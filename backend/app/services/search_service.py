"""Cross-app search: one function per result group, scored and ranked in Python.

Everything here is ILIKE, matching the rest of this codebase
(services/project_service.py, services/task_service.py, services/chat_service.py,
agents/chat_tools.py's project_search tool) — there is no tsvector, pg_trgm, or GIN index
anywhere in this schema, and introducing full-text search for a search bar over one
user's tens-to-low-hundreds of rows would be a migration and a ranking model to maintain
for no measurable win. If per-user row counts ever reach the thousands, the swap point is
the two `_search_*` functions that hit the DB — the scoring and the response shape are
unaffected.

Scoring is computed in Python after fetching, for the same reason
portfolio_service.technology_frequency_from_projects counts in Python: the candidate set
is small, and a SQL CASE expression that reproduces _FIELD_WEIGHTS would be the harder
thing to read and change.
"""

from urllib.parse import quote
from uuid import UUID

from langchain_core.messages import HumanMessage, SystemMessage
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.chatbot_graph import stringify_content
from app.core.ownership import owned
from app.models.ai_provider_setting import ProviderName
from app.models.project import Project
from app.models.task import Task
from app.models.user import User
from app.providers.base import ProviderError
from app.providers.prompts import SEARCH_ANSWER_SYSTEM_PROMPT, build_search_answer_prompt
from app.providers.registry import get_provider, resolve_default_provider
from app.schemas.search import SearchAnswer, SearchGroup, SearchHit, SearchResponse
from app.search.app_features import APP_FEATURES
from app.services.portfolio_service import compute_technology_frequency
from app.services.usage_service import record_usage

# Which field a query matched, and what that's worth. A name match is the strongest
# signal a search bar has; a hit buried in a 10,000-character long description is the
# weakest. The two *_short fields rank above the *_long ones — they're what the UI
# actually shows in compact views, so a hit there is more relevant to surface first.
_FIELD_WEIGHTS = {"name": 100, "role": 60, "technology": 50, "short": 30, "long": 10}
_PREFIX_BONUS = 25
_EXACT_BONUS = 50
_CANDIDATE_CAP = 50


def _text_score(field: str, value: str, q: str) -> float:
    v = value.lower()
    score = float(_FIELD_WEIGHTS.get(field, 10))
    if v == q:
        score += _EXACT_BONUS
    elif v.startswith(q):
        score += _PREFIX_BONUS
    return score


async def _search_projects(db: AsyncSession, user_id: UUID, q: str) -> list[SearchHit]:
    pattern = f"%{q}%"
    stmt = (
        owned(Project, user_id)
        .where(
            or_(
                Project.name.ilike(pattern),
                Project.role.ilike(pattern),
                Project.description_short_text.ilike(pattern),
                Project.responsibilities_short_text.ilike(pattern),
                Project.description_long_text.ilike(pattern),
                Project.responsibilities_long_text.ilike(pattern),
            )
        )
        .order_by(Project.is_current.desc(), Project.start_date.desc())
        .limit(_CANDIDATE_CAP)
    )
    projects = (await db.execute(stmt)).scalars().all()

    ql = q.lower()
    hits: list[SearchHit] = []
    for p in projects:
        best = 0.0
        for field, value in (
            ("name", p.name),
            ("role", p.role),
            ("short", p.description_short_text),
            ("short", p.responsibilities_short_text),
            ("long", p.description_long_text),
            ("long", p.responsibilities_long_text),
        ):
            if value and ql in value.lower():
                best = max(best, _text_score(field, value, ql))
        hits.append(
            SearchHit(
                kind="project",
                id=str(p.id),
                title=p.name,
                subtitle=p.role,
                snippet=p.description_short_text[:160],
                href=f"/projects/{p.id}",
                score=best,
                meta={"is_current": p.is_current},
            )
        )
    return hits


async def _search_technologies(db: AsyncSession, user_id: UUID, q: str) -> list[SearchHit]:
    freq = await compute_technology_frequency(db, user_id)
    ql = q.lower()
    hits: list[SearchHit] = []
    for entry in freq["technologies"]:
        name = entry["name"]
        if ql not in name.lower():
            continue
        hits.append(
            SearchHit(
                kind="technology",
                id=name.lower(),
                title=name,
                subtitle=f"{entry['project_count']} project{'s' if entry['project_count'] != 1 else ''}",
                href=f"/projects?technology={quote(name)}",
                score=_text_score("technology", name, ql) + entry["project_count"],
                meta={"project_count": entry["project_count"]},
            )
        )
    return hits


async def _search_tasks(db: AsyncSession, user_id: UUID, q: str) -> list[SearchHit]:
    pattern = f"%{q}%"
    stmt = (
        owned(Task, user_id)
        .where(or_(Task.title.ilike(pattern), Task.description.ilike(pattern)))
        .order_by(Task.due_date.asc().nulls_last(), Task.updated_at.desc())
        .limit(_CANDIDATE_CAP)
    )
    tasks = (await db.execute(stmt)).scalars().all()

    ql = q.lower()
    hits: list[SearchHit] = []
    for t in tasks:
        best = _text_score("name", t.title, ql) if ql in t.title.lower() else _text_score("long", t.description, ql)
        hits.append(
            SearchHit(
                kind="task",
                id=str(t.id),
                title=t.title,
                subtitle=t.status.value.replace("_", " ").title(),
                snippet=t.description[:160],
                href=f"/projects/{t.project_id}/tasks?task={t.id}",
                score=best,
                meta={"status": t.status.value, "priority": t.priority.value, "project_id": str(t.project_id)},
            )
        )
    return hits


def _search_app_features(q: str) -> list[SearchHit]:
    """AND-over-tokens: every whitespace-split token of `q` must hit somewhere (title,
    keywords, or description) for a feature to match at all — this is what makes
    "upload spreadsheet" resolve to the Brag Document entry (via its "upload"/"spreadsheet"
    keywords) while "upload zebra" correctly returns nothing, rather than a looser OR
    match returning every feature that merely mentions "upload"."""
    tokens = [t for t in q.lower().split() if t]
    if not tokens:
        return []

    hits: list[SearchHit] = []
    for feature in APP_FEATURES:
        total = 0.0
        matched_all = True
        for token in tokens:
            token_score = 0.0
            if token in feature.title.lower():
                token_score = max(token_score, _text_score("name", feature.title, token))
            for kw in feature.keywords:
                if token in kw.lower():
                    token_score = max(token_score, 70.0)
            if token in feature.description.lower():
                token_score = max(token_score, 25.0)
            if token_score == 0.0:
                matched_all = False
                break
            total += token_score
        if not matched_all:
            continue
        hits.append(
            SearchHit(
                kind="app_feature",
                id=feature.slug,
                title=feature.title,
                subtitle="",
                snippet=feature.description,
                href=feature.path,
                score=total,
            )
        )
    return hits


_GROUP_LABELS = {"project": "Projects", "technology": "Technologies", "task": "Tasks", "app_feature": "Pages & features"}


async def search(db: AsyncSession, user_id: UUID, q: str, *, limit_per_group: int = 5) -> SearchResponse:
    project_hits = sorted(await _search_projects(db, user_id, q), key=lambda h: h.score, reverse=True)
    tech_hits = sorted(await _search_technologies(db, user_id, q), key=lambda h: h.score, reverse=True)
    task_hits = sorted(await _search_tasks(db, user_id, q), key=lambda h: h.score, reverse=True)
    feature_hits = sorted(_search_app_features(q), key=lambda h: h.score, reverse=True)

    groups = [
        SearchGroup(kind="project", label=_GROUP_LABELS["project"], items=project_hits[:limit_per_group], total=len(project_hits)),
        SearchGroup(kind="technology", label=_GROUP_LABELS["technology"], items=tech_hits[:limit_per_group], total=len(tech_hits)),
        SearchGroup(kind="task", label=_GROUP_LABELS["task"], items=task_hits[:limit_per_group], total=len(task_hits)),
        SearchGroup(kind="app_feature", label=_GROUP_LABELS["app_feature"], items=feature_hits[:limit_per_group], total=len(feature_hits)),
    ]
    total = sum(g.total for g in groups)
    return SearchResponse(q=q, groups=groups, total=total)


async def answer_question(
    db: AsyncSession, user: User, q: str, *, provider_override: ProviderName | None = None
) -> SearchAnswer:
    """One grounded LLM call for the dashboard search bar's "ask Jarvis" row.

    Deliberately NOT the chatbot graph (agents/chatbot_graph.py): no tools, no session,
    no history. A single grounded question isn't a conversation, and routing it through
    stream_chat would mean inventing a throwaway ChatSession row just to hold it. Grounds
    the answer in this same search()'s top hits (so it's tied to the user's *real* saved
    rows, not the model's imagination) plus the platform guide, via
    providers/prompts.build_search_answer_prompt.
    """
    results = await search(db, user.id, q, limit_per_group=8)
    top_hits = [h.model_dump() for group in results.groups for h in group.items][:8]

    # Resolved once, up front, so the same ProviderName is used both to build the
    # provider adapter AND to tag the usage-log row below — mirrors
    # chat_service.stream_turn's own pattern (LLMProvider has no public "which provider
    # is this" property, only a model name).
    resolved_provider = provider_override or await resolve_default_provider(db, user.id)
    provider = await get_provider(db, user.id, resolved_provider, purpose="search_answer")
    model = provider.get_chat_model()
    response = await model.ainvoke(
        [
            SystemMessage(content=SEARCH_ANSWER_SYSTEM_PROMPT),
            HumanMessage(content=build_search_answer_prompt(q, top_hits)),
        ]
    )

    usage = getattr(response, "usage_metadata", None)
    if usage:
        await record_usage(
            db, user_id=user.id, provider=resolved_provider, model=provider.model,
            operation="search_answer", usage=usage,
        )

    answer_text = stringify_content(response.content) or "I couldn't find an answer to that."
    citations = [h for group in results.groups for h in group.items if h.score > 0][:5]
    return SearchAnswer(answer=answer_text, citations=citations)


__all__ = ["search", "answer_question"]
