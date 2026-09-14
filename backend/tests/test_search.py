"""services/search_service.search — ranking, cross-user isolation, and the app-features
group. No LLM involved (search() is the fast SQL half; answer_question is not exercised
here since it needs a configured provider)."""

from datetime import date

import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.project import Project
from app.models.task import Task
from app.models.user import User
from app.services import search_service


@pytest_asyncio.fixture
async def searchable_projects(db: AsyncSession, user_a: User) -> list[Project]:
    exact = Project(
        user_id=user_a.id,
        name="Zephyr",
        role="Engineer",
        start_date=date(2026, 1, 1),
        is_current=True,
        description_long_text="A long description that happens to mention Zephyr deep inside a lot of other text " * 5,
        technologies=["Python", "React"],
    )
    other = Project(
        user_id=user_a.id,
        name="Unrelated Project",
        role="Engineer",
        start_date=date(2025, 1, 1),
        is_current=False,
        description_long_text="Zephyr is mentioned only once, buried in a long paragraph of unrelated text " * 5,
        technologies=["Go"],
    )
    db.add_all([exact, other])
    await db.commit()
    for p in (exact, other):
        await db.refresh(p)
    return [exact, other]


@pytest_asyncio.fixture
async def other_users_project(db: AsyncSession, user_b: User) -> Project:
    p = Project(
        user_id=user_b.id,
        name="Zephyr",  # same name as user_a's — must never leak across users
        role="Engineer",
        start_date=date(2026, 1, 1),
        is_current=True,
        technologies=["Zephyr-Tech"],
    )
    db.add(p)
    await db.commit()
    await db.refresh(p)
    return p


@pytest_asyncio.fixture
async def searchable_task(db: AsyncSession, user_a: User, searchable_projects: list[Project]) -> Task:
    task = Task(
        user_id=user_a.id,
        project_id=searchable_projects[0].id,
        title="Fix the Zephyr login bug",
        description="",
    )
    db.add(task)
    await db.commit()
    await db.refresh(task)
    return task


async def test_project_name_match_ranks_above_long_description_match(
    db: AsyncSession, user_a: User, searchable_projects: list[Project]
):
    result = await search_service.search(db, user_a.id, "zephyr")
    project_group = next(g for g in result.groups if g.kind == "project")
    titles = [h.title for h in project_group.items]
    assert titles[0] == "Zephyr"  # the exact name match must rank first


async def test_technology_group_matches_compute_technology_frequency(
    db: AsyncSession, user_a: User, searchable_projects: list[Project]
):
    result = await search_service.search(db, user_a.id, "python")
    tech_group = next(g for g in result.groups if g.kind == "technology")
    assert any(h.title == "Python" for h in tech_group.items)


async def test_task_group_matches_by_title(
    db: AsyncSession, user_a: User, searchable_task: Task
):
    result = await search_service.search(db, user_a.id, "login bug")
    task_group = next(g for g in result.groups if g.kind == "task")
    assert any(h.id == str(searchable_task.id) for h in task_group.items)


async def test_app_feature_multi_token_and_match(db: AsyncSession, user_a: User):
    result = await search_service.search(db, user_a.id, "upload spreadsheet")
    feature_group = next(g for g in result.groups if g.kind == "app_feature")
    assert any(h.id == "brag-document" for h in feature_group.items)


async def test_app_feature_nonsense_token_matches_nothing(db: AsyncSession, user_a: User):
    result = await search_service.search(db, user_a.id, "upload zebra")
    feature_group = next(g for g in result.groups if g.kind == "app_feature")
    assert feature_group.items == []


async def test_cross_user_leakage_none(
    db: AsyncSession, user_a: User, searchable_projects: list[Project], other_users_project: Project
):
    """The one test that catches a missing `user_id ==` predicate in a new query."""
    result = await search_service.search(db, user_a.id, "zephyr")
    for group in result.groups:
        for hit in group.items:
            if group.kind == "project":
                assert hit.id != str(other_users_project.id)
            if group.kind == "technology":
                assert hit.title != "Zephyr-Tech"


async def test_limit_per_group_truncates_but_total_reports_real_count(
    db: AsyncSession, user_a: User, searchable_projects: list[Project]
):
    result = await search_service.search(db, user_a.id, "e", limit_per_group=1)
    project_group = next(g for g in result.groups if g.kind == "project")
    assert len(project_group.items) <= 1
    assert project_group.total >= len(project_group.items)
