import asyncio
import logging
from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import CurrentUser
from app.core.ownership import require_owned
from app.models.breakdown_job import BreakdownJob
from app.models.document import Document
from app.models.extraction_job import JobStatus
from app.models.project import Project
from app.models.task import Task
from app.models.user import User
from app.providers.registry import resolve_default_provider
from app.schemas.breakdown import (
    BreakdownAcceptRequest,
    BreakdownAcceptResponse,
    BreakdownCreateRequest,
    BreakdownDismissRequest,
    BreakdownJobCreated,
    BreakdownJobOut,
    BreakdownSkippedItem,
    LLMBreakdownResult,
)
from app.schemas.task import TaskOut
from app.services import breakdown_service, task_service
from app.workers.settings import enqueue_breakdown, request_cancel

logger = logging.getLogger(__name__)

# Project-scoped (creation only needs the project's ownership checked once); every other
# route is flat by-id on the job itself, same reasoning as routers/tasks.py's split.
router = APIRouter(prefix="/projects", tags=["breakdowns"])
breakdown_jobs_router = APIRouter(prefix="/breakdown-jobs", tags=["breakdowns"])

_CANCELLABLE = (JobStatus.QUEUED, JobStatus.PARSING, JobStatus.EXTRACTING, JobStatus.STRUCTURING)


def _to_out(job: BreakdownJob) -> BreakdownJobOut:
    return BreakdownJobOut(
        id=job.id,
        status=job.status.value,
        document_id=job.document_id,
        prompt=job.prompt,
        max_tasks=job.max_tasks,
        is_scanned=job.is_scanned,
        result=LLMBreakdownResult.model_validate(job.result) if job.result else None,
        accepted={ref: UUID(task_id) for ref, task_id in job.accepted_refs.items()},
        dismissed_refs=list(job.dismissed_refs),
        error_code=job.error_code,
        error_message=job.error_message,
    )


def _task_to_out(task: Task, counts: dict[UUID, tuple[int, int]] | None = None) -> TaskOut:
    total, done = (counts or {}).get(task.id, (0, 0))
    return TaskOut(
        id=task.id,
        project_id=task.project_id,
        parent_id=task.parent_id,
        title=task.title,
        description=task.description,
        status=task.status,
        priority=task.priority,
        source=task.source,
        estimate_minutes=task.estimate_minutes,
        due_date=task.due_date,
        position=task.position,
        completed_at=task.completed_at,
        created_at=task.created_at,
        updated_at=task.updated_at,
        subtask_total=total,
        subtask_done=done,
    )


@router.post(
    "/{project_id}/breakdowns", response_model=BreakdownJobCreated, status_code=status.HTTP_201_CREATED
)
async def create_breakdown(
    project_id: UUID,
    payload: BreakdownCreateRequest,
    user: User = CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> BreakdownJobCreated:
    project = await require_owned(db, Project, project_id, user.id, resource="Project")

    if payload.document_id is not None:
        # Re-validated here, not trusted from the client: a document_id belonging to
        # another user (or nobody) must 404 exactly like every other owned lookup.
        await require_owned(db, Document, payload.document_id, user.id, resource="Document")

    resolved_provider = payload.provider or await resolve_default_provider(db, user.id)
    job = BreakdownJob(
        user_id=user.id,
        project_id=project.id,
        document_id=payload.document_id,
        provider=resolved_provider,
        prompt=payload.prompt,
        max_tasks=payload.max_tasks,
    )
    db.add(job)
    await db.commit()
    await db.refresh(job)

    await enqueue_breakdown(job.id)

    return BreakdownJobCreated(id=job.id)


@breakdown_jobs_router.get("/{job_id}", response_model=BreakdownJobOut)
async def get_breakdown_job(
    job_id: UUID, user: User = CurrentUser, db: AsyncSession = Depends(get_db)
) -> BreakdownJobOut:
    job = await require_owned(db, BreakdownJob, job_id, user.id, resource="Breakdown job")
    return _to_out(job)


@breakdown_jobs_router.post("/{job_id}/cancel", response_model=BreakdownJobOut)
async def cancel_breakdown_job(
    job_id: UUID, user: User = CurrentUser, db: AsyncSession = Depends(get_db)
) -> BreakdownJobOut:
    job = await require_owned(db, BreakdownJob, job_id, user.id, resource="Breakdown job")

    if job.status in _CANCELLABLE:
        job.status = JobStatus.CANCELLED
        job.error_code = "CANCELLED"
        job.error_message = "Cancelled by user"
        job.finished_at = datetime.now(UTC)
        await db.commit()

        try:
            await asyncio.wait_for(request_cancel(job.id), timeout=5)
        except Exception:
            logger.exception("Failed to signal SAQ abort for cancelled breakdown job %s", job.id)

    return _to_out(job)


@breakdown_jobs_router.post("/{job_id}/accept", response_model=BreakdownAcceptResponse)
async def accept_breakdown(
    job_id: UUID,
    payload: BreakdownAcceptRequest,
    user: User = CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> BreakdownAcceptResponse:
    job = await require_owned(db, BreakdownJob, job_id, user.id, resource="Breakdown job")
    project = await require_owned(db, Project, job.project_id, user.id, resource="Project")

    created, skipped, promoted_refs = await breakdown_service.accept_breakdown_items(
        db, user.id, project, job, payload.items, dry_run=payload.dry_run
    )
    counts = await task_service.subtask_counts(db, user.id, [t.id for t in created])
    return BreakdownAcceptResponse(
        created=[_task_to_out(t, counts) for t in created],
        skipped=[BreakdownSkippedItem(**s) for s in skipped],
        promoted_refs=promoted_refs,
    )


@breakdown_jobs_router.post("/{job_id}/dismiss", response_model=BreakdownJobOut)
async def dismiss_breakdown(
    job_id: UUID,
    payload: BreakdownDismissRequest,
    user: User = CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> BreakdownJobOut:
    job = await require_owned(db, BreakdownJob, job_id, user.id, resource="Breakdown job")
    job = await breakdown_service.dismiss_breakdown_refs(db, job, payload.refs)
    return _to_out(job)
