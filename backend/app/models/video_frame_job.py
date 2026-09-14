import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.base import UUIDPk
from app.models.extraction_job import JobStatus, job_status_enum


class VideoFrameJob(Base, UUIDPk):
    """Minimal, write-only-from-the-frontend audit row: created and enqueued the moment a
    video upload/replace succeeds (routers/project_media.py::upload_video), never polled —
    there is no status endpoint, no cancel endpoint, no frontend hook. The carousel simply
    appears whenever ProjectVideoFrame rows exist next time the project page loads, same
    as FAQJob.

    Still gets a real job table (rather than "no row at all, just try/except in the
    request") for two reasons worth the ceremony even with zero consumers: (1)
    reap_stale_jobs' crash-safety sweep is one line to extend and catches a worker that
    died mid-extraction, which would otherwise be silently invisible forever; (2)
    error_code/error_message give a corrupt/unsupported uploaded video a real audit trail
    instead of only a log line.

    video_media_id is SET NULL (not CASCADE, unlike ProjectVideoFrame) — this row is an
    audit log that should survive the video/frames it described being replaced or
    deleted, mirroring ThumbnailJob.media_id's own SET NULL.
    """

    __tablename__ = "video_frame_jobs"

    user_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    video_media_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("project_media.id", ondelete="SET NULL"), nullable=True
    )

    status: Mapped[JobStatus] = mapped_column(job_status_enum, default=JobStatus.QUEUED, nullable=False, index=True)
    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
