"""Cron job: any job stuck in a non-terminal state for too long (a crashed worker, a hung
provider call) is marked failed/TIMEOUT so the frontend's poll always terminates
(backend/DESIGN.md §6). Sweeps both job tables in the same cron tick — a crashed worker
doesn't care which table its job belonged to, and this is one extra SELECT/UPDATE pair
in a cron that already runs every 5 minutes, not a second cron.
"""

from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import async_session_factory
from app.models.brag_document_job import BragDocumentJob
from app.models.breakdown_job import BreakdownJob
from app.models.extraction_job import ExtractionJob, JobStatus

_STALE_AFTER = timedelta(minutes=10)
_NON_TERMINAL = (JobStatus.QUEUED, JobStatus.PARSING, JobStatus.EXTRACTING, JobStatus.STRUCTURING)


async def _reap(db: AsyncSession, model, cutoff: datetime) -> int:
    rows = (
        await db.execute(select(model).where(model.status.in_(_NON_TERMINAL), model.created_at < cutoff))
    ).scalars().all()
    for job in rows:
        job.status = JobStatus.FAILED
        job.error_code = "TIMEOUT"
        job.error_message = "The job did not complete in time (the worker may have crashed)."
        job.finished_at = datetime.now(UTC)
    return len(rows)


async def reap_stale_jobs(ctx) -> None:
    cutoff = datetime.now(UTC) - _STALE_AFTER
    async with async_session_factory() as db:
        reaped = await _reap(db, ExtractionJob, cutoff)
        reaped += await _reap(db, BreakdownJob, cutoff)
        reaped += await _reap(db, BragDocumentJob, cutoff)
        if reaped:
            await db.commit()
