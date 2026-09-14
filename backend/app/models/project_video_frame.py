import uuid

from sqlalchemy import BigInteger, ForeignKey, Integer, LargeBinary, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.base import Timestamps, UUIDPk


class ProjectVideoFrame(Base, UUIDPk, Timestamps):
    """One extracted still frame from a project's video, metadata-only — mirrors
    ProjectMedia/ProjectMediaBlob's split (models/project_media.py): bytes live in
    ProjectVideoFrameBlob below with no relationship() back, reached only via an explicit
    select in services/video_frame_service.py.

    video_media_id (not project_id) carries ON DELETE CASCADE: replacing or deleting the
    project's video (project_media_service.replace_media does delete-then-insert) cascades
    away every frame belonging to the old video automatically — no explicit "clear old
    frames" code is needed anywhere in routers/project_media.py, the same way
    ProjectMediaBlob rows already vanish for free when their ProjectMedia row is deleted.

    UniqueConstraint(video_media_id, order_index) keeps re-running extraction for the same
    video idempotent, the same way uq_project_media_project_kind does for uploads.
    """

    __tablename__ = "project_video_frames"
    __table_args__ = (
        UniqueConstraint("video_media_id", "order_index", name="uq_video_frame_media_order"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    video_media_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("project_media.id", ondelete="CASCADE"), nullable=False, index=True
    )

    order_index: Mapped[int] = mapped_column(Integer, nullable=False)
    mime_type: Mapped[str] = mapped_column(String(255), nullable=False)  # always "image/jpeg"
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    # Doubles as the HTTP ETag and as the ?v= cache-buster in the served URL — same
    # convention as ProjectMedia.sha256.
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)


class ProjectVideoFrameBlob(Base):
    """Bytes only. No user_id (reachable only through ProjectVideoFrame, which carries the
    ownership predicate), no relationship back — same reasoning as ProjectMediaBlob.
    Frames are small (a few hundred KB JPEG each) so, unlike video, they're read whole via
    a single SELECT (services/video_frame_service.py), never range-served."""

    __tablename__ = "project_video_frame_blobs"

    frame_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("project_video_frames.id", ondelete="CASCADE"),
        primary_key=True,
    )
    data: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
