"""SAQ task functions — thin wrappers over the framework-agnostic services, per
backend/DESIGN.md §6, so business logic stays unit-testable with no queue involved.
"""

from uuid import UUID

from app.core.database import async_session_factory
from app.services.chat_service import compact_history as _compact_history
from app.services.chat_service import generate_session_title as _generate_session_title
from app.services.extraction_service import run_extraction_job as _run_extraction_job
from app.services.suggestion_service import (
    recompute_user_suggestions as _recompute_user_suggestions,
)


async def run_extraction_job(ctx, job_id: str) -> None:
    async with async_session_factory() as db:
        await _run_extraction_job(db, UUID(job_id))


async def generate_session_title(ctx, session_id: str) -> None:
    async with async_session_factory() as db:
        await _generate_session_title(db, UUID(session_id))


async def compact_history(ctx, session_id: str) -> None:
    async with async_session_factory() as db:
        await _compact_history(db, UUID(session_id))


async def recompute_user_suggestions(ctx, user_id: str) -> None:
    async with async_session_factory() as db:
        await _recompute_user_suggestions(db, UUID(user_id))
