import uuid
from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.ai_provider_setting import ProviderName, provider_name_enum
from app.models.base import UUIDPk
from app.models.extraction_job import JobStatus, job_status_enum


class BragDocumentJob(Base, UUIDPk):
    """One "standup Excel + saved project context -> LLM-drafted monthly brag document"
    job. Reuses ExtractionJob's exact `job_status` enum type (see extraction_job.py's
    job_status_enum) so the 4-stage stepper, cancel endpoint, and stale-job reaper all
    keep working unchanged — same reasoning as BreakdownJob (models/breakdown_job.py),
    whose docstring explains why this is its own table rather than a `kind`
    discriminator.

    No project_id, unlike BreakdownJob: this job spans potentially many of the user's
    projects for one calendar month, so there is no single project to scope the row to.

    `result` and `hour_stats` are deliberately separate JSON columns, not one blob:
    `result` holds only the LLM-authored prose sections (schemas.brag_document.
    LLMBragDocumentResult), while `hour_stats` holds the deterministic arithmetic computed
    by services/standup_excel_service.aggregate_member_month (schemas.brag_document.
    HourStatsOut). Keeping them apart means the LLM's output can never overwrite the hour
    math this feature's trust story depends on — the export renderer and the API response
    both read `hour_stats` for any hour/date figure, never `result`.
    """

    __tablename__ = "brag_document_jobs"

    user_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    document_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False
    )

    provider: Mapped[ProviderName] = mapped_column(provider_name_enum, nullable=False)
    status: Mapped[JobStatus] = mapped_column(job_status_enum, default=JobStatus.QUEUED, nullable=False, index=True)

    # Defaults to f"{target_month} Brag Document" at creation time (routers/brag_documents.py,
    # agents/chat_tools.py) — always set explicitly in Python, never a DB-level default, so
    # every creation path stays in one place. Editable later if a rename UI is ever added.
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    member_name: Mapped[str] = mapped_column(String(200), nullable=False)
    target_month: Mapped[str] = mapped_column(String(20), nullable=False)  # e.g. "August 2026"

    result: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    hour_stats: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
