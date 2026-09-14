import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.ai_provider_setting import ProviderName, provider_name_enum
from app.models.base import UUIDPk
from app.models.extraction_job import JobStatus, job_status_enum


class ThumbnailJob(Base, UUIDPk):
    """One "project context -> generated thumbnail" job. Reuses ExtractionJob's
    `job_status` enum (extraction_job.job_status_enum) so the existing 4-stage stepper,
    the cancel endpoint's request_cancel (workers/settings.py:121-133), and the stale-job
    reaper (workers/stale_jobs.py) all work unchanged — same reasoning as
    models/breakdown_job.py's docstring, and its own table for the same reason.

    Stage mapping for this job's status ladder (see services/thumbnail_service.py):
      PARSING     -> assembling the prompt from the project's own saved fields
      EXTRACTING  -> calling the image model
      STRUCTURING -> the image model was unavailable/failed; designing an SVG poster
                     spec with the text model instead
    A job that succeeds on the image model never enters STRUCTURING, so "did we fall
    back?" is answerable from `generator` on the resulting media row, not from status.
    """

    __tablename__ = "thumbnail_jobs"

    user_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )

    provider: Mapped[ProviderName] = mapped_column(provider_name_enum, nullable=False)
    status: Mapped[JobStatus] = mapped_column(
        job_status_enum, default=JobStatus.QUEUED, nullable=False, index=True
    )

    media_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("project_media.id", ondelete="SET NULL"), nullable=True
    )
    generator: Mapped[str | None] = mapped_column(String(32), nullable=True)

    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
