"""Shared fixtures for the backend test suite.

Postgres is required — SQLite is not an option. This schema uses native Postgres enums
(task_status, task_priority, task_source, ...), ARRAY columns, JSONB, and Identity()
columns, none of which SQLite has an equivalent for. Point TEST_DATABASE_URL at a real,
throwaway Postgres database before running these tests (defaults to a sibling `aipm_test`
database on the same docker-compose Postgres instance the app itself uses — see
docker-compose.yml at the repo root). This is the number-one wasted afternoon on this
repo if skipped.

DATABASE_URL is set from TEST_DATABASE_URL *before* importing anything from `app` —
app/core/database.py builds its async engine at import time from whatever DATABASE_URL is
in the environment then, so setting it any later has no effect.
"""

import os
import uuid
from collections.abc import AsyncIterator
from datetime import date

os.environ["DATABASE_URL"] = os.environ.get(
    "TEST_DATABASE_URL", "postgresql+asyncpg://aipm:aipm@localhost:5433/aipm_test"
)
os.environ.setdefault("SECRET_KEY", "test-secret-key-not-for-production-use-only")
os.environ.setdefault("FERNET_KEY", "6qF2mZ8pQ4vN0xR7tY3wA1bC5sD9eG2hJ4kM6nP8qS0=")

import pytest_asyncio
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import Base, async_session_factory, engine
from app.core.deps import get_current_user
from app.core.ownership import ResourceNotFoundError
from app.models.project import Project
from app.models.user import User
from app.routers import tasks
from app.services.task_service import TaskValidationError


def _build_app() -> FastAPI:
    """A minimal FastAPI app carrying only the task routers and the two exception
    handlers they rely on — deliberately NOT app.main.app, whose lifespan starts a
    Playwright Chromium instance and spawns a SAQ worker child process, neither of which
    any task test needs."""
    app = FastAPI()
    app.include_router(tasks.router, prefix="/api/v1")
    app.include_router(tasks.tasks_router, prefix="/api/v1")

    @app.exception_handler(ResourceNotFoundError)
    async def _not_found(request, exc: ResourceNotFoundError) -> JSONResponse:
        return JSONResponse(status_code=404, content={"detail": f"{exc.resource} not found"})

    @app.exception_handler(TaskValidationError)
    async def _validation(request, exc: TaskValidationError) -> JSONResponse:
        return JSONResponse(status_code=422, content={"detail": str(exc)})

    return app


@pytest_asyncio.fixture(scope="session", autouse=True)
async def _schema() -> AsyncIterator[None]:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    await engine.dispose()


@pytest_asyncio.fixture(autouse=True)
async def _clean_tables() -> AsyncIterator[None]:
    """Function-scoped cleanup, run after each test. TRUNCATE ... CASCADE rather than a
    nested-transaction/savepoint rollback: get_db and every service function call
    db.commit() directly against their own session, so a savepoint strategy would need
    every service under test to participate in a transaction they don't know exists."""
    yield
    async with engine.begin() as conn:
        await conn.execute(text("TRUNCATE users, projects, tasks RESTART IDENTITY CASCADE"))


@pytest_asyncio.fixture
async def db() -> AsyncIterator[AsyncSession]:
    async with async_session_factory() as session:
        yield session


@pytest_asyncio.fixture
async def user_a(db: AsyncSession) -> User:
    user = User(email=f"a-{uuid.uuid4()}@example.com", hashed_password="x", first_name="A")
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


@pytest_asyncio.fixture
async def user_b(db: AsyncSession) -> User:
    user = User(email=f"b-{uuid.uuid4()}@example.com", hashed_password="x", first_name="B")
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


@pytest_asyncio.fixture
async def project_a(db: AsyncSession, user_a: User) -> Project:
    project = Project(
        user_id=user_a.id, name="Project A", role="Engineer", start_date=date(2026, 1, 1), is_current=True
    )
    db.add(project)
    await db.commit()
    await db.refresh(project)
    return project


@pytest_asyncio.fixture
async def project_b(db: AsyncSession, user_b: User) -> Project:
    project = Project(
        user_id=user_b.id, name="Project B", role="Engineer", start_date=date(2026, 1, 1), is_current=True
    )
    db.add(project)
    await db.commit()
    await db.refresh(project)
    return project


@pytest_asyncio.fixture
async def client_a(user_a: User) -> AsyncIterator[AsyncClient]:
    app = _build_app()
    app.dependency_overrides[get_current_user] = lambda: user_a
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client


@pytest_asyncio.fixture
async def client_b(user_b: User) -> AsyncIterator[AsyncClient]:
    app = _build_app()
    app.dependency_overrides[get_current_user] = lambda: user_b
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client


@pytest_asyncio.fixture
async def client_no_auth() -> AsyncIterator[AsyncClient]:
    """No dependency_overrides at all — exercises the REAL get_current_user dependency
    against a request with no Authorization header, so a route that accidentally omits
    `user: User = CurrentUser` entirely can't hide behind an override that's always
    applied everywhere else in the suite."""
    app = _build_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client
