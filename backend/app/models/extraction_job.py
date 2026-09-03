import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import JSON, DateTime, Enum, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.ai_provider_setting import ProviderName, provider_name_enum
from app.models.base import UUIDPk


class JobStatus(StrEnum):
    QUEUED = "queued"
    PARSING = "parsing"
    EXTRACTING = "extracting"
    STRUCTURING = "structuring"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


# Shared Enum instance, same reasoning as provider_name_enum/task_status_enum — declared
# once so the Postgres TYPE isn't emitted twice. BreakdownJob (models/breakdown_job.py)
# reuses this exact enum instead of declaring its own — same stage names, same cancel
# semantics, same stale-job reaper — so a migration adding a breakdown_jobs.status column
# must reference this TYPE with create_type=False rather than re-declaring the enum.
job_status_enum = Enum(JobStatus, name="job_status")


class ExtractionJob(Base, UUIDPk):
    """status doubles as the frontend's poll `stage` while pending (queued -> parsing ->
    extracting -> structuring), see backend/DESIGN.md §6 for the full state machine and
    the reap_stale_jobs cron that guarantees a poll always terminates.
    """

    __tablename__ = "extraction_jobs"

    user_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    document_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False
    )
    project_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("projects.id", ondelete="SET NULL"), nullable=True
    )

    provider: Mapped[ProviderName] = mapped_column(provider_name_enum, nullable=False)
    status: Mapped[JobStatus] = mapped_column(
        job_status_enum, default=JobStatus.QUEUED, nullable=False, index=True
    )

    result: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
