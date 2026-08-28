"""Cron job: any extraction_job stuck in a non-terminal state for too long (a crashed
worker, a hung provider call) is marked failed/TIMEOUT so the frontend's poll always
terminates (backend/DESIGN.md §6).
"""

from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from app.core.database import async_session_factory
from app.models.extraction_job import ExtractionJob, JobStatus

_STALE_AFTER = timedelta(minutes=10)
_NON_TERMINAL = (JobStatus.QUEUED, JobStatus.PARSING, JobStatus.EXTRACTING, JobStatus.STRUCTURING)


async def reap_stale_jobs(ctx) -> None:
    cutoff = datetime.now(UTC) - _STALE_AFTER
    async with async_session_factory() as db:
        rows = (
            await db.execute(
                select(ExtractionJob).where(
                    ExtractionJob.status.in_(_NON_TERMINAL),
                    ExtractionJob.created_at < cutoff,
                )
            )
        ).scalars().all()
        for job in rows:
            job.status = JobStatus.FAILED
            job.error_code = "TIMEOUT"
            job.error_message = "The job did not complete in time (the worker may have crashed)."
            job.finished_at = datetime.now(UTC)
        if rows:
            await db.commit()
