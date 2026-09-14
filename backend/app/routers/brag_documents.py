"""Endpoints for the Brag Document Generator feature. Split into two routers, same
reasoning as routers/breakdown.py's split: `router` (prefix /brag-documents) covers the
synchronous preview + job-creation entry points, `brag_document_jobs_router` (prefix
/brag-document-jobs) is flat by-id on the job itself.
"""

import asyncio
import logging
from datetime import UTC, datetime
from uuid import UUID

from fastapi import (
    APIRouter,
    Depends,
    File,
    HTTPException,
    Query,
    Request,
    Response,
    UploadFile,
    status,
)
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.database import get_db
from app.core.deps import CurrentUser
from app.core.ownership import require_owned
from app.ingest.extract import UnsupportedFormatError
from app.models.brag_document_job import BragDocumentJob
from app.models.document import Document
from app.models.extraction_job import JobStatus
from app.models.user import User
from app.providers.registry import resolve_default_provider
from app.schemas.brag_document import (
    BragDocumentCreateRequest,
    BragDocumentJobCreated,
    BragDocumentJobListResponse,
    BragDocumentJobOut,
    BragDocumentJobSummary,
    BragDocumentPreviewResponse,
    HourStatsOut,
    LLMBragDocumentResult,
)
from app.services.brag_document_export_service import export_brag_document
from app.services.brag_document_service import default_brag_document_name
from app.services.document_service import UploadTooLargeError, save_upload
from app.services.standup_excel_service import (
    MEMBER_MATCH_CONFIDENCE_THRESHOLD,
    best_member_match,
    parse_standup_workbook,
)
from app.workers.settings import enqueue_brag_document, request_cancel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/brag-documents", tags=["brag-documents"])
brag_document_jobs_router = APIRouter(prefix="/brag-document-jobs", tags=["brag-documents"])

_CANCELLABLE = (JobStatus.QUEUED, JobStatus.PARSING, JobStatus.EXTRACTING, JobStatus.STRUCTURING)


@router.post("/preview", response_model=BragDocumentPreviewResponse, status_code=status.HTTP_201_CREATED)
async def preview_brag_document(
    file: UploadFile = File(...),
    user: User = CurrentUser,
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> BragDocumentPreviewResponse:
    """Parses the uploaded standup workbook synchronously (no job row yet) and returns
    the auto-detected member match, the full candidate list for a manual dropdown
    fallback, and the months available to generate a document for. The document itself
    is still stored via document_service.save_upload (storage/hashing), so its id can be
    handed straight to POST /brag-documents once the user confirms member + month.
    """
    data = await file.read()
    filename = file.filename or "upload.xlsx"

    try:
        workbook = parse_standup_workbook(data, filename)
    except Exception as exc:
        logger.exception("Failed to parse uploaded standup workbook")
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            {"code": "PARSE_ERROR", "message": f"Could not parse this spreadsheet: {exc}"},
        ) from exc

    try:
        document = await save_upload(db, settings, user_id=user.id, filename=filename, data=data)
    except UnsupportedFormatError as exc:
        raise HTTPException(status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, {"code": exc.code, "message": exc.message}) from exc
    except UploadTooLargeError as exc:
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, str(exc)) from exc

    detected_name, confidence = best_member_match(workbook.team_members, user.full_name)
    if confidence < MEMBER_MATCH_CONFIDENCE_THRESHOLD:
        detected_name = None

    return BragDocumentPreviewResponse(
        document_id=document.id,
        detected_member_name=detected_name,
        match_confidence=confidence,
        candidate_member_names=workbook.team_members,
        available_months=workbook.available_months,
    )


@router.post("", response_model=BragDocumentJobCreated, status_code=status.HTTP_201_CREATED)
async def create_brag_document(
    payload: BragDocumentCreateRequest,
    user: User = CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> BragDocumentJobCreated:
    # Re-validated here, not trusted from the client: a document_id belonging to another
    # user (or nobody) must 404 exactly like every other owned lookup.
    await require_owned(db, Document, payload.document_id, user.id, resource="Document")

    resolved_provider = payload.provider or await resolve_default_provider(db, user.id)
    job = BragDocumentJob(
        user_id=user.id,
        document_id=payload.document_id,
        provider=resolved_provider,
        name=payload.name or default_brag_document_name(payload.target_month),
        member_name=payload.member_name,
        target_month=payload.target_month,
    )
    db.add(job)
    await db.commit()
    await db.refresh(job)

    await enqueue_brag_document(job.id)

    return BragDocumentJobCreated(id=job.id)


def _to_out(job: BragDocumentJob) -> BragDocumentJobOut:
    effective_result = job.effective_result
    return BragDocumentJobOut(
        id=job.id,
        name=job.name,
        status=job.status.value,
        document_id=job.document_id,
        member_name=job.member_name,
        target_month=job.target_month,
        result=LLMBragDocumentResult.model_validate(effective_result) if effective_result else None,
        is_edited=job.edited_result is not None,
        hour_stats=HourStatsOut.model_validate(job.hour_stats) if job.hour_stats else None,
        error_code=job.error_code,
        error_message=job.error_message,
    )


@brag_document_jobs_router.get("", response_model=BragDocumentJobListResponse)
async def list_brag_document_jobs(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user: User = CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> BragDocumentJobListResponse:
    """The saved-documents list shown on the Brag Documents page when no specific job is
    open — every generated document is already persisted (nothing here is a separate
    "save" step), so this is just that history, most recent first."""
    base = select(BragDocumentJob).where(BragDocumentJob.user_id == user.id)
    total = (
        await db.execute(select(func.count()).select_from(base.subquery()))
    ).scalar_one()
    stmt = (
        base.order_by(BragDocumentJob.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    jobs = list((await db.execute(stmt)).scalars().all())
    return BragDocumentJobListResponse(
        items=[
            BragDocumentJobSummary(
                id=j.id,
                name=j.name,
                status=j.status.value,
                member_name=j.member_name,
                target_month=j.target_month,
                created_at=j.created_at,
            )
            for j in jobs
        ],
        total=total,
    )


@brag_document_jobs_router.get("/{job_id}", response_model=BragDocumentJobOut)
async def get_brag_document_job(
    job_id: UUID, user: User = CurrentUser, db: AsyncSession = Depends(get_db)
) -> BragDocumentJobOut:
    job = await require_owned(db, BragDocumentJob, job_id, user.id, resource="Brag document job")
    return _to_out(job)


@brag_document_jobs_router.patch("/{job_id}", response_model=BragDocumentJobOut)
async def update_brag_document_result(
    job_id: UUID,
    payload: LLMBragDocumentResult,
    user: User = CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> BragDocumentJobOut:
    """Saves the user's manually-edited version of the drafted document (text edits,
    and/or removed bullets/groups/impact areas) — the whole edited shape is sent and
    replaces any previous edit whole-sale, same as autosaving a document. Never touches
    `result` itself; see BragDocumentJob.edited_result's docstring."""
    job = await require_owned(db, BragDocumentJob, job_id, user.id, resource="Brag document job")
    if job.status != JobStatus.SUCCEEDED:
        raise HTTPException(
            status.HTTP_409_CONFLICT, "This brag document hasn't finished generating yet."
        )
    job.edited_result = payload.model_dump()
    await db.commit()
    await db.refresh(job)
    return _to_out(job)


@brag_document_jobs_router.post("/{job_id}/reset", response_model=BragDocumentJobOut)
async def reset_brag_document_edits(
    job_id: UUID, user: User = CurrentUser, db: AsyncSession = Depends(get_db)
) -> BragDocumentJobOut:
    """Discards every saved edit, reverting the effective result back to the original
    LLM draft in `result` — a plain "set edited_result back to NULL", nothing to
    validate since `result` itself was never touched."""
    job = await require_owned(db, BragDocumentJob, job_id, user.id, resource="Brag document job")
    job.edited_result = None
    await db.commit()
    await db.refresh(job)
    return _to_out(job)


@brag_document_jobs_router.delete("/{job_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_brag_document_job(
    job_id: UUID, user: User = CurrentUser, db: AsyncSession = Depends(get_db)
) -> None:
    job = await require_owned(db, BragDocumentJob, job_id, user.id, resource="Brag document job")
    if job.status in _CANCELLABLE:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "This brag document is still generating — cancel it before deleting, or wait for it to finish.",
        )
    await db.delete(job)
    await db.commit()


@brag_document_jobs_router.post("/{job_id}/cancel", response_model=BragDocumentJobOut)
async def cancel_brag_document_job(
    job_id: UUID, user: User = CurrentUser, db: AsyncSession = Depends(get_db)
) -> BragDocumentJobOut:
    job = await require_owned(db, BragDocumentJob, job_id, user.id, resource="Brag document job")

    if job.status in _CANCELLABLE:
        job.status = JobStatus.CANCELLED
        job.error_code = "CANCELLED"
        job.error_message = "Cancelled by user"
        job.finished_at = datetime.now(UTC)
        await db.commit()

        try:
            await asyncio.wait_for(request_cancel(job.id), timeout=5)
        except Exception:
            logger.exception("Failed to signal SAQ abort for cancelled brag document job %s", job.id)

    return _to_out(job)


@brag_document_jobs_router.get("/{job_id}/export")
async def export_brag_document_job(
    job_id: UUID,
    request: Request,
    format: str = Query(pattern="^(pdf|docx)$"),
    user: User = CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> Response:
    job = await require_owned(db, BragDocumentJob, job_id, user.id, resource="Brag document job")
    if job.status != JobStatus.SUCCEEDED:
        raise HTTPException(status.HTTP_409_CONFLICT, "This brag document hasn't finished generating yet.")

    browser = getattr(request.app.state, "browser", None)
    content, content_type, filename = await export_brag_document(job, format, browser)

    return Response(
        content=content,
        media_type=content_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
