"""services/dashboard_service.build_summary — the aggregate endpoint behind the
dashboard. The zero-project path is the real crash risk in an aggregate endpoint, so it
gets its own test."""

from datetime import date

import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.project import Project
from app.models.user import User
from app.services import dashboard_service


@pytest_asyncio.fixture
async def multi_tech_projects(db: AsyncSession, user_a: User) -> list[Project]:
    p1 = Project(
        user_id=user_a.id, name="P1", role="Engineer", start_date=date(2026, 1, 1),
        is_current=True, technologies=["Python", "React"],
    )
    p2 = Project(
        user_id=user_a.id, name="P2", role="Engineer", start_date=date(2025, 1, 1),
        is_current=False, technologies=["Python", "Go"],
    )
    db.add_all([p1, p2])
    await db.commit()
    for p in (p1, p2):
        await db.refresh(p)
    return [p1, p2]


async def test_zero_projects_returns_empty_summary_not_500(db: AsyncSession, user_a: User):
    summary = await dashboard_service.build_summary(db, user_a.id)
    assert summary.total_projects == 0
    assert summary.current_projects == 0
    assert summary.technologies == []
    assert summary.distinct_technology_count == 0
    assert summary.projects == []


async def test_totals_and_ranking(db: AsyncSession, user_a: User, multi_tech_projects: list[Project]):
    summary = await dashboard_service.build_summary(db, user_a.id)
    assert summary.total_projects == 2
    assert summary.current_projects == 1
    # Python appears in both projects, so it must rank first.
    assert summary.technologies[0].name == "Python"
    assert summary.technologies[0].project_count == 2
    assert summary.distinct_technology_count == 3  # Python, React, Go


async def test_top_technologies_caps_list_but_not_distinct_count(
    db: AsyncSession, user_a: User, multi_tech_projects: list[Project]
):
    summary = await dashboard_service.build_summary(db, user_a.id, top_technologies=1)
    assert len(summary.technologies) == 1
    assert summary.distinct_technology_count == 3


async def test_cross_user_isolation(db: AsyncSession, user_a: User, user_b: User, multi_tech_projects: list[Project]):
    summary_b = await dashboard_service.build_summary(db, user_b.id)
    assert summary_b.total_projects == 0
