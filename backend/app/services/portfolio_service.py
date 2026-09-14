from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.project import Project


def technology_frequency_from_projects(projects: list[Project]) -> dict:
    """The counting half of compute_technology_frequency, split out so a caller that
    already holds the project list (services/dashboard_service.build_summary) doesn't
    re-SELECT the same rows. Both existing callers keep the async DB-querying form below.

    Normalized (lowercased) for counting since `technologies` is free-text with no
    controlled vocabulary/casing guarantee — a Python pass over this user's own project
    set (tens to low hundreds of rows) is simpler and clearer than a SQL aggregate here.
    """
    counts: dict[str, int] = {}
    display: dict[str, str] = {}
    for p in projects:
        for t in p.technologies:
            key = t.lower()
            counts[key] = counts.get(key, 0) + 1
            display.setdefault(key, t)
    ranked = sorted(counts.items(), key=lambda kv: kv[1], reverse=True)
    return {
        "technologies": [{"name": display[key], "project_count": count} for key, count in ranked],
        "total_projects": len(projects),
    }


async def compute_technology_frequency(db: AsyncSession, user_id: UUID) -> dict:
    """How many of the user's projects use each technology, most-used first. Standalone
    extraction of chat_tools.portfolio_analysis's technology_frequency branch so both the
    LangChain tool and the background suggestion job (suggestion_service.py) share one
    implementation."""
    stmt = select(Project).where(Project.user_id == user_id)
    projects = list((await db.execute(stmt)).scalars().all())
    return technology_frequency_from_projects(projects)
