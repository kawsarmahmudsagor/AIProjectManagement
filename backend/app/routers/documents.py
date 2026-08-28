from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.database import get_db
from app.core.deps import CurrentUser
from app.ingest.extract import UnsupportedFormatError
from app.models.ai_provider_setting import ProviderName
from app.models.extraction_job import ExtractionJob
from app.models.user import User
from app.schemas.document import UploadResponse
from app.providers.registry import resolve_default_provider
from app.services.document_service import UploadTooLargeError, save_upload
from app.workers.settings import enqueue_extraction

router = APIRouter(prefix="/documents", tags=["documents"])


@router.post("", response_model=UploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_document(
    file: UploadFile = File(...),
    project_id: UUID | None = Form(default=None),
    provider: ProviderName | None = Form(default=None),
    user: User = CurrentUser,
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> UploadResponse:
    data = await file.read()

    try:
        document = await save_upload(
            db, settings, user_id=user.id, filename=file.filename or "upload",
            data=data, project_id=project_id,
        )
    except UnsupportedFormatError as exc:
        raise HTTPException(status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, {"code": exc.code, "message": exc.message}) from exc
    except UploadTooLargeError as exc:
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, str(exc)) from exc

    resolved_provider = provider or await resolve_default_provider(db, user.id)
    job = ExtractionJob(
        user_id=user.id, document_id=document.id, project_id=project_id, provider=resolved_provider
    )
    db.add(job)
    await db.commit()
    await db.refresh(job)

    await enqueue_extraction(job.id)

    return UploadResponse(document_id=document.id, job_id=job.id)
