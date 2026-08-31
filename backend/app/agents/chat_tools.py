"""Jarvis's three tools. Built per chat-turn (`build_tools`), not as module-level
singletons like the rest of this codebase prefers to do things — this is required here
because all three close over one request's `db`/`user_id`, which must never be
LLM-visible tool-call arguments (the model could otherwise be prompted into pointing a
tool at another user's data). For github_search this closure isn't about scoping a query
to this user's rows (GitHub itself is queried the same way regardless of caller) — it's
so the tool can check/record this user's suggestion history via
app.services.suggestion_service, so it never repeats a repo already suggested to them
(here or on the Dashboard's proactive suggestions card — see
app.services.suggestion_service.recompute_user_suggestions).

Only github_search talks outside this user's own data — project_search/portfolio_analysis
are read-only queries against this same user's rows, scoped by user_id at the SQL layer,
not by prompt instruction.
"""

import json
from typing import Literal
from uuid import UUID

from langchain_core.tools import BaseTool, tool
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.project import Project
from app.services.github_service import search_github_repos
from app.services.portfolio_service import compute_technology_frequency
from app.services.suggestion_service import get_suggested_repo_full_names, record_chat_suggestions

TOOL_LABELS = {
    "project_search": "Searching your projects…",
    "portfolio_analysis": "Analyzing your portfolio…",
    "github_search": "Searching GitHub…",
}


def build_tools(db: AsyncSession, user_id: UUID) -> list[BaseTool]:
    # response_format="content_and_artifact": each tool below returns (content, artifact)
    # — `content` is the JSON string the LLM reads, `artifact` is the same data as a raw
    # dict, attached to the resulting ToolMessage.artifact untouched by any string
    # round-trip. agents/chatbot_graph.py reads `.artifact` (falling back to parsing
    # `.content` if a given LangChain version doesn't preserve it) so the structured
    # shape below is exactly what's stored in ChatMessage.tool_result and rendered as
    # rich cards (e.g. GitHub repos) by the frontend, with no re-parsing.

    @tool(response_format="content_and_artifact")
    async def project_search(
        query: str | None = None, technologies: list[str] | None = None, limit: int = 10
    ) -> tuple[str, dict]:
        """Search the current user's own saved projects by free-text query and/or
        required technologies. Use this whenever the user asks anything about their own
        projects, work history, or which of their projects use a given technology.
        Returns up to `limit` matching projects (current/most recent first) with name,
        role, dates, technologies, and short description/responsibilities text. If both
        `query` and `technologies` are omitted, returns the user's most recent projects."""
        stmt = select(Project).where(Project.user_id == user_id)
        if query:
            pattern = f"%{query}%"
            stmt = stmt.where(
                or_(
                    Project.name.ilike(pattern),
                    Project.role.ilike(pattern),
                    Project.description_long_text.ilike(pattern),
                    Project.responsibilities_long_text.ilike(pattern),
                )
            )
        stmt = stmt.order_by(Project.is_current.desc(), Project.start_date.desc())
        projects = list((await db.execute(stmt)).scalars().all())

        if technologies:
            # Filtered in Python (not SQL) for simple case-insensitive matching against
            # the free-text `technologies` array — same reasoning as portfolio_analysis
            # below, and correct at this table's expected per-user scale.
            wanted = {t.lower() for t in technologies}
            projects = [p for p in projects if wanted & {t.lower() for t in p.technologies}]

        projects = projects[:limit]
        result = {
            "projects": [
                {
                    "id": str(p.id),
                    "name": p.name,
                    "role": p.role,
                    "start_date": p.start_date.isoformat(),
                    "end_date": p.end_date.isoformat() if p.end_date else None,
                    "is_current": p.is_current,
                    "technologies": p.technologies,
                    # _text variants only — never _html — the LLM never needs markup.
                    "description_short_text": p.description_short_text,
                    "responsibilities_short_text": p.responsibilities_short_text,
                }
                for p in projects
            ],
            "count": len(projects),
        }
        return json.dumps(result), result

    @tool(response_format="content_and_artifact")
    async def portfolio_analysis(
        focus: Literal["technology_frequency", "technology_pairs", "timeline", "roles"],
        technologies: list[str] | None = None,
    ) -> tuple[str, dict]:
        """Analyze patterns across ALL of the current user's saved projects. Use this for
        cross-project questions like "which technologies do I use most", "what are my
        strongest technical areas", "which projects use both X and Y", or "show me my
        project timeline" — never for a question about one named project (use
        project_search for that). `focus` selects the aggregate:
        - technology_frequency: how many projects use each technology, most-used first.
        - technology_pairs: which projects use ALL of the given `technologies` together
          (required for this focus).
        - timeline: every project in chronological order.
        - roles: how many projects the user held each role on.
        This tool only returns factual counts/lists — it never judges what counts as a
        "strongest" area itself; that interpretation is yours to make from the data."""
        if focus == "technology_frequency":
            result = await compute_technology_frequency(db, user_id)
            return json.dumps(result), result

        stmt = select(Project).where(Project.user_id == user_id)
        projects = list((await db.execute(stmt)).scalars().all())

        if focus == "technology_pairs":
            wanted = {t.lower() for t in (technologies or [])}
            matches = [p for p in projects if wanted <= {t.lower() for t in p.technologies}]
            result = {
                "projects": [
                    {"id": str(p.id), "name": p.name, "technologies": p.technologies} for p in matches
                ]
            }

        elif focus == "timeline":
            ordered = sorted(projects, key=lambda p: p.start_date)
            result = {
                "projects": [
                    {
                        "id": str(p.id),
                        "name": p.name,
                        "start_date": p.start_date.isoformat(),
                        "end_date": p.end_date.isoformat() if p.end_date else None,
                        "is_current": p.is_current,
                    }
                    for p in ordered
                ]
            }

        else:  # focus == "roles"
            role_counts: dict[str, int] = {}
            for p in projects:
                role_counts[p.role] = role_counts.get(p.role, 0) + 1
            ranked_roles = sorted(role_counts.items(), key=lambda kv: kv[1], reverse=True)
            result = {"roles": [{"role": role, "project_count": count} for role, count in ranked_roles]}

        return json.dumps(result), result

    @tool(response_format="content_and_artifact")
    async def github_search(query: str, limit: int = 5) -> tuple[str, dict]:
        """Search GitHub for real, currently well-maintained open-source repositories
        matching `query` (a technology, framework, or topic — e.g. "RAG framework
        python"). Use this to ground any specific repo recommendation instead of
        recalling one from memory, since your training data may be stale on stars or
        maintenance status. Only returns repos above a minimum star count that have
        pushed a commit within roughly the last year and are not archived. Never repeats
        a repo already suggested to this user, in this conversation or a past one."""
        limit = min(max(limit, 1), 10)
        already_suggested = await get_suggested_repo_full_names(db, user_id)

        # Over-fetch so filtering out repos this user has already seen still leaves
        # `limit` results where possible, without a second API call.
        result = await search_github_repos(query, limit=min(limit + 5, 10))
        if result.get("error"):
            return json.dumps(result), result

        fresh_repos = [r for r in result["repos"] if r["full_name"] not in already_suggested][:limit]
        await record_chat_suggestions(db, user_id, query, fresh_repos)

        result = {"repos": fresh_repos, "query_used": result["query_used"]}
        return json.dumps(result), result

    return [project_search, portfolio_analysis, github_search]
