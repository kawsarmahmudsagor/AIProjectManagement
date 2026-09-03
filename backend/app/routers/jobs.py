import asyncio
import logging
from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import CurrentUser
from app.core.ownership import require_owned
from app.models.extraction_job import ExtractionJob, JobStatus
from app.models.user import User
from app.schemas.common import ErrorDetail
from app.schemas.job import ExtractionResult, JobStatusOut
from app.workers.settings import request_cancel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/extraction-jobs", tags=["jobs"])

_CANCELLABLE = (JobStatus.QUEUED, JobStatus.PARSING, JobStatus.EXTRACTING, JobStatus.STRUCTURING)


def _to_out(job: ExtractionJob) -> JobStatusOut:
    return JobStatusOut(
        id=job.id,
        status=job.status,
        result=ExtractionResult.model_validate(job.result) if job.result else None,
        error=(
            ErrorDetail(code=job.error_code, message=job.error_message, provider=job.provider.value)
            if job.error_code
            else None
        ),
    )


@router.get("/{job_id}", response_model=JobStatusOut)
async def get_job_status(
    job_id: UUID, user: User = CurrentUser, db: AsyncSession = Depends(get_db)
) -> JobStatusOut:
    job = await require_owned(db, ExtractionJob, job_id, user.id, resource="Job")
    return _to_out(job)


@router.post("/{job_id}/cancel", response_model=JobStatusOut)
async def cancel_job(
    job_id: UUID, user: User = CurrentUser, db: AsyncSession = Depends(get_db)
) -> JobStatusOut:
    job = await require_owned(db, ExtractionJob, job_id, user.id, resource="Job")

    if job.status in _CANCELLABLE:
        # Mark the row cancelled first — the frontend's poll should stop treating this
        # as in-progress immediately, regardless of how long the worker takes to notice
        # the abort request.
        job.status = JobStatus.CANCELLED
        job.error_code = "CANCELLED"
        job.error_message = "Cancelled by user"
        job.finished_at = datetime.now(UTC)
        await db.commit()

        # The DB row is already truthful at this point — the frontend's poll (and this
        # response) will show it as cancelled regardless of what happens below. Bound
        # and swallow failures here so a slow/unreachable SAQ worker can't make the
        # cancel button itself hang or error out from the user's point of view.
        try:
            await asyncio.wait_for(request_cancel(job.id), timeout=5)
        except Exception:
            logger.exception("Failed to signal SAQ abort for cancelled job %s", job.id)

    return _to_out(job)
