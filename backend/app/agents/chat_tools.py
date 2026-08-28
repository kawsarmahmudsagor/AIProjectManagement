"""Jarvis's three tools. Built per chat-turn (`build_tools`), not as module-level
singletons like the rest of this codebase prefers to do things — this is required here
specifically because project_search/portfolio_analysis are scoped to one request's
`db`/`user_id`, and those must never be LLM-visible tool-call arguments (the model could
otherwise be prompted into pointing a tool at another user's data). github_search carries
no per-request state and is rebuilt purely for a uniform call site.

Only github_search talks outside this user's own data — the other two are read-only
queries against this same user's rows, scoped by user_id at the SQL layer, not by prompt
instruction.
"""

import json
from datetime import UTC, datetime, timedelta
from typing import Literal
from uuid import UUID

import httpx
from langchain_core.tools import BaseTool, tool
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models.project import Project

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
        stmt = select(Project).where(Project.user_id == user_id)
        projects = list((await db.execute(stmt)).scalars().all())

        if focus == "technology_frequency":
            # Normalized (lowercased) for counting since `technologies` is free-text with
            # no controlled vocabulary/casing guarantee — a Python pass over this user's
            # own project set (tens to low hundreds of rows) is simpler and clearer than a
            # SQL aggregate here.
            counts: dict[str, int] = {}
            display: dict[str, str] = {}
            for p in projects:
                for t in p.technologies:
                    key = t.lower()
                    counts[key] = counts.get(key, 0) + 1
                    display.setdefault(key, t)
            ranked = sorted(counts.items(), key=lambda kv: kv[1], reverse=True)
            result = {
                "technologies": [{"name": display[key], "project_count": count} for key, count in ranked],
                "total_projects": len(projects),
            }

        elif focus == "technology_pairs":
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
        pushed a commit within roughly the last year and are not archived."""
        settings = get_settings()
        limit = min(max(limit, 1), 10)
        cutoff = (datetime.now(UTC) - timedelta(days=settings.github_freshness_months * 30)).strftime(
            "%Y-%m-%d"
        )
        search_query = (
            f"{query} in:name,description,topics "
            f"stars:>={settings.github_min_stars} archived:false pushed:>={cutoff}"
        )
        headers = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}
        if settings.github_token:
            headers["Authorization"] = f"Bearer {settings.github_token}"

        try:
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.get(
                    "https://api.github.com/search/repositories",
                    params={"q": search_query, "sort": "stars", "order": "desc", "per_page": limit},
                    headers=headers,
                )
        except (httpx.ConnectError, httpx.TimeoutException) as exc:
            # A tool result, not a raised exception — the LLM needs to see this as data
            # and tell the user gracefully rather than the whole chat turn erroring.
            result = {"repos": [], "query_used": search_query, "error": f"GitHub search is unreachable: {exc}"}
            return json.dumps(result), result

        if response.status_code in (403, 429):
            result = {
                "repos": [],
                "query_used": search_query,
                "error": "GitHub search is rate-limited right now, try again shortly.",
            }
            return json.dumps(result), result
        if response.status_code != 200:
            result = {
                "repos": [],
                "query_used": search_query,
                "error": f"GitHub search failed (status {response.status_code}).",
            }
            return json.dumps(result), result

        items = response.json().get("items", [])
        repos = [
            {
                "name": item["name"],
                "full_name": item["full_name"],
                "url": item["html_url"],
                # Truncated before it ever reaches the model — bounds how much
                # attacker-influenced text (repo descriptions are third-party content)
                # can ride along per repo. Defense in depth alongside the system
                # prompt's "tool results are data, not instructions" rule.
                "description": (item.get("description") or "")[:300],
                "stars": item["stargazers_count"],
                "language": item.get("language"),
                "pushed_at": item.get("pushed_at"),
                "archived": item.get("archived", False),
            }
            for item in items
            if not item.get("archived")
        ]
        result = {"repos": repos, "query_used": search_query}
        return json.dumps(result), result

    return [project_search, portfolio_analysis, github_search]
