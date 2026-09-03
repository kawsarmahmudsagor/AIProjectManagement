import uuid
from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.ai_provider_setting import ProviderName, provider_name_enum
from app.models.base import UUIDPk
from app.models.extraction_job import JobStatus, job_status_enum


class BreakdownJob(Base, UUIDPk):
    """One "document/prompt -> proposed task tree" job. Reuses ExtractionJob's exact
    `job_status` enum type (see extraction_job.py's job_status_enum) so the 4-stage
    stepper, cancel endpoint, and stale-job reaper all keep working unchanged — see
    backend/DESIGN.md §6. Deliberately its own table rather than a `kind` discriminator on
    ExtractionJob: that table hard-codes `ExtractionResult.model_validate(job.result)` in
    routers/jobs.py, and its document_id is NOT NULL while project_id is nullable — the
    exact inverse of what a breakdown job needs (project_id required, document_id optional
    for a prompt-only breakdown).

    accepted_refs maps a proposed task's `ref` to the *created* Task's id (as a string),
    not just a flag — this is what lets a second `/accept` call (a user reviewing 40 items
    in two passes) resolve a later batch's `parent_ref` against a task created in an
    earlier batch, and lets a duplicate submission of the same ref be recognized and
    skipped rather than creating another copy.
    """

    __tablename__ = "breakdown_jobs"

    user_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    document_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("documents.id", ondelete="SET NULL"), nullable=True
    )

    provider: Mapped[ProviderName] = mapped_column(provider_name_enum, nullable=False)
    status: Mapped[JobStatus] = mapped_column(job_status_enum, default=JobStatus.QUEUED, nullable=False, index=True)

    prompt: Mapped[str | None] = mapped_column(Text, nullable=True)
    max_tasks: Mapped[int] = mapped_column(Integer, default=25, nullable=False)
    is_scanned: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    result: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    accepted_refs: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    dismissed_refs: Mapped[list] = mapped_column(JSON, default=list, nullable=False)

    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
