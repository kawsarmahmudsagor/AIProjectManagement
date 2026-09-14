import uuid
from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.ai_provider_setting import ProviderName, provider_name_enum
from app.models.base import UUIDPk
from app.models.extraction_job import JobStatus, job_status_enum


class FAQJob(Base, UUIDPk):
    """One "project fields -> curated FAQ" job, created automatically at project-creation
    time (routers/projects.py::create_project) — never user-triggered, no status endpoint,
    no cancel endpoint. Reuses ExtractionJob's job_status_enum for the same reason
    ThumbnailJob/BreakdownJob do (see their docstrings): the stale-job reaper works
    unchanged.

    There is deliberately no `Project.faq` column and no copy-back step: `result` on this
    row IS the source of truth, read live by routers/projects.py::_to_out() via
    services/faq_service.get_latest_result() (latest SUCCEEDED row for the project) —
    exactly like BreakdownJob.result is read live elsewhere rather than folded onto a
    parent row. No unique constraint on project_id: a project gets exactly one job today
    (created once, never re-triggered), so "latest by created_at" is unambiguous; a
    regenerate feature, if ever added, stays correct with no migration since it would just
    create another row and let the same "latest SUCCEEDED wins" read pick it up.
    """

    __tablename__ = "faq_jobs"

    user_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )

    provider: Mapped[ProviderName] = mapped_column(provider_name_enum, nullable=False)
    status: Mapped[JobStatus] = mapped_column(job_status_enum, default=JobStatus.QUEUED, nullable=False, index=True)

    result: Mapped[dict | None] = mapped_column(JSON, nullable=True)  # LLMFAQResult.model_dump(mode="json")

    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
