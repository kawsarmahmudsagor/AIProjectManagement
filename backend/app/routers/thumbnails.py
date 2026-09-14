import asyncio
import logging
from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import CurrentUser
from app.core.ownership import require_owned
from app.models.extraction_job import JobStatus
from app.models.project import Project
from app.models.project_media import MediaKind
from app.models.thumbnail_job import ThumbnailJob
from app.models.user import User
from app.providers.registry import resolve_default_provider
from app.schemas.common import ErrorDetail
from app.schemas.project_media import ThumbnailGenerateRequest, ThumbnailGenerateResponse, ThumbnailJobOut
from app.services import project_media_service, thumbnail_service
from app.workers.settings import enqueue_thumbnail, request_cancel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/projects", tags=["thumbnails"])
thumbnail_jobs_router = APIRouter(prefix="/thumbnail-jobs", tags=["thumbnails"])

_CANCELLABLE = (JobStatus.QUEUED, JobStatus.PARSING, JobStatus.EXTRACTING, JobStatus.STRUCTURING)


def _to_out(job: ThumbnailJob) -> ThumbnailJobOut:
    """`result` is left None here — a successful job's media_id points at a ProjectMedia
    row this function doesn't have loaded, and cancel/enqueue callers never need it.
    get_thumbnail_job below is the one caller that fills it in, via a real lookup."""
    return ThumbnailJobOut(
        id=job.id,
        status=job.status.value,
        result=None,
        error=ErrorDetail(code=job.error_code, message=job.error_message) if job.error_code else None,
    )


@router.post("/{project_id}/thumbnail/generate", response_model=ThumbnailGenerateResponse, status_code=status.HTTP_201_CREATED)
async def generate_thumbnail(
    project_id: UUID,
    payload: ThumbnailGenerateRequest,
    user: User = CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> ThumbnailGenerateResponse:
    """The precondition check runs here, synchronously, before any job row is created —
    it's a pure DB/request predicate with zero LLM cost, and a job that immediately fails
    would show a spinner then an error, strictly worse than an inline 422. Re-checked
    again inside run_thumbnail_job itself, since the project can be edited between
    enqueue and run."""
    project = await require_owned(db, Project, project_id, user.id, resource="Project")

    ctx = payload.context
    if not thumbnail_service.has_sufficient_context(
        description_text=ctx.description_text or project.description_long_text or project.description_short_text,
        responsibilities_text=ctx.responsibilities_text
        or project.responsibilities_long_text
        or project.responsibilities_short_text,
        technologies=ctx.technologies or project.technologies,
    ):
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            {"code": "INSUFFICIENT_PROJECT_CONTEXT", "message": thumbnail_service.INSUFFICIENT_CONTEXT_MESSAGE},
        )

    resolved_provider = await resolve_default_provider(db, user.id)
    job = ThumbnailJob(user_id=user.id, project_id=project_id, provider=resolved_provider)
    db.add(job)
    await db.commit()
    await db.refresh(job)

    await enqueue_thumbnail(job.id)

    return ThumbnailGenerateResponse(job_id=job.id)


@thumbnail_jobs_router.get("/{job_id}", response_model=ThumbnailJobOut)
async def get_thumbnail_job(
    job_id: UUID, user: User = CurrentUser, db: AsyncSession = Depends(get_db)
) -> ThumbnailJobOut:
    job = await require_owned(db, ThumbnailJob, job_id, user.id, resource="Thumbnail job")
    out = _to_out(job)
    if job.status == JobStatus.SUCCEEDED and job.media_id is not None:
        media = await project_media_service.get_media(db, user.id, job.project_id, MediaKind.THUMBNAIL)
        out.result = project_media_service.media_ref(job.project_id, media)
    return out


@thumbnail_jobs_router.post("/{job_id}/cancel", response_model=ThumbnailJobOut)
async def cancel_thumbnail_job(
    job_id: UUID, user: User = CurrentUser, db: AsyncSession = Depends(get_db)
) -> ThumbnailJobOut:
    job = await require_owned(db, ThumbnailJob, job_id, user.id, resource="Thumbnail job")

    if job.status in _CANCELLABLE:
        job.status = JobStatus.CANCELLED
        job.error_code = "CANCELLED"
        job.error_message = "Cancelled by user"
        job.finished_at = datetime.now(UTC)
        await db.commit()

        try:
            await asyncio.wait_for(request_cancel(job.id), timeout=5)
        except Exception:
            logger.exception("Failed to signal SAQ abort for cancelled thumbnail job %s", job.id)

    return _to_out(job)
