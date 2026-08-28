"""SAQ task functions — thin wrappers over the framework-agnostic services, per
backend/DESIGN.md §6, so business logic stays unit-testable with no queue involved.
"""

from uuid import UUID

from app.core.database import async_session_factory
from app.services.extraction_service import run_extraction_job as _run_extraction_job


async def run_extraction_job(ctx, job_id: str) -> None:
    async with async_session_factory() as db:
        await _run_extraction_job(db, UUID(job_id))
