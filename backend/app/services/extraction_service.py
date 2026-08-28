"""Orchestrates one extraction job: ingest -> provider call -> persist result.

This is called by both the SAQ worker task (app/workers/tasks.py) and directly in tests —
it takes a plain AsyncSession and has no dependency on FastAPI or the queue, per
backend/DESIGN.md §1 ("services are thin wrappers ... exactly what the SAQ task calls").
"""

import logging
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.richtext import html_to_text, sanitize_html, wrap_html
from app.ingest.extract import UnsupportedFormatError, ingest
from app.models.document import Document
from app.models.extraction_job import ExtractionJob, JobStatus
from app.models.user import AgentPersona, User
from app.providers.base import ExtractInput, ProviderError
from app.providers.registry import get_provider
from app.providers.schema_utils import inline_refs
from app.schemas.common import RichText
from app.schemas.job import ExtractedProject, ExtractionResult, LLMExtractionResult
from app.schemas.project import ProjectSection

logger = logging.getLogger(__name__)

_EXTRACTION_SCHEMA = inline_refs(LLMExtractionResult.model_json_schema())


def _to_section(long_text: str | None, short_text: str | None) -> ProjectSection:
    long_html = sanitize_html(wrap_html(long_text)) if (long_text or "").strip() else ""
    short_html = sanitize_html(wrap_html(short_text)) if (short_text or "").strip() else ""
    return ProjectSection(
        long=RichText(html=long_html, text=html_to_text(long_html)),
        short=RichText(html=short_html, text=html_to_text(short_html)),
    )


def _to_extraction_result(llm_result: LLMExtractionResult) -> ExtractionResult:
    p = llm_result.project
    return ExtractionResult(
        project=ExtractedProject(
            name=p.name,
            role=p.role,
            start_date=p.start_date,
            end_date=p.end_date,
            description=_to_section(p.description_long, p.description_short),
            responsibilities=_to_section(p.responsibilities_long, p.responsibilities_short),
            technologies=p.technologies,
        ),
        confidence_notes=llm_result.confidence_notes,
    )


async def _fail(db: AsyncSession, job: ExtractionJob, code: str, message: str) -> None:
    job.status = JobStatus.FAILED
    job.error_code = code
    job.error_message = message
    job.finished_at = datetime.now(UTC)
    await db.commit()


async def run_extraction_job(db: AsyncSession, job_id: UUID) -> None:
    job = await db.get(ExtractionJob, job_id)
    if job is None:
        logger.error("extraction job %s not found", job_id)
        return

    document = await db.get(Document, job.document_id)
    if document is None:
        await _fail(db, job, "DOCUMENT_MISSING", "The uploaded document is missing")
        return

    job.status = JobStatus.PARSING
    job.started_at = datetime.now(UTC)
    await db.commit()

    try:
        try:
            data = Path(document.storage_path).read_bytes()
            parsed = ingest(data, document.filename)
        except UnsupportedFormatError as exc:
            await _fail(db, job, exc.code, exc.message)
            return
        except OSError as exc:
            await _fail(db, job, "STORAGE_ERROR", f"Could not read the uploaded file: {exc}")
            return

        if parsed.is_scanned and not parsed.raw_bytes:
            await _fail(
                db, job, "NO_TEXT_FOUND",
                "This looks like a scanned document with no extractable text.",
            )
            return

        job.status = JobStatus.EXTRACTING
        await db.commit()

        try:
            provider = await get_provider(db, job.user_id, job.provider, purpose="extract")
            user = await db.get(User, job.user_id)
            persona = user.agent_persona if user else AgentPersona.BUSINESS_ANALYST
            raw_result = await provider.extract(
                ExtractInput(
                    raw_bytes=parsed.raw_bytes if parsed.mime_type == "application/pdf" else None,
                    mime_type=parsed.mime_type,
                    extracted_text=parsed.extracted_text,
                    filename=document.filename,
                ),
                json_schema=_EXTRACTION_SCHEMA,
                persona=persona,
            )
        except ProviderError as exc:
            await _fail(db, job, exc.code, exc.message)
            return

        job.status = JobStatus.STRUCTURING
        await db.commit()

        try:
            llm_result = LLMExtractionResult.model_validate(raw_result)
        except ValidationError as exc:
            await _fail(
                db, job, "INVALID_PROVIDER_OUTPUT",
                f"The AI's response didn't match the expected structure: {exc.error_count()} field(s) invalid.",
            )
            return

        result = _to_extraction_result(llm_result)

        job.result = result.model_dump(mode="json")
        job.status = JobStatus.SUCCEEDED
        job.finished_at = datetime.now(UTC)
        await db.commit()
    except Exception:
        # Anything not already turned into a _fail() call above is a bug or an
        # unclassified provider/library failure (e.g. a shape LangChain returns that
        # ProviderError-handling doesn't know about). Without this, the job row is stuck
        # at whatever status was last committed until the 10-minute stale-job reaper
        # (reap_stale_jobs) catches it, and a Cancel click against a job whose worker
        # already died has nothing left to actually stop in the meantime.
        logger.exception("Unexpected error running extraction job %s", job_id)
        await db.rollback()
        await _fail(
            db, job, "UNEXPECTED_ERROR",
            "Something went wrong while processing this document. Please try again.",
        )
