"""Optional thumbnail image and optional video for a Project, stored as Postgres bytea
rather than on disk — a deliberate departure from the on-disk precedent in
services/document_service.py and services/profile_service.py, chosen so media travels
with the database (no second backup/restore surface, no orphaned files after a failed
delete). Three mitigations make that affordable and they are all load-bearing:

1. The bytes live in their own table (ProjectMediaBlob below). There is intentionally NO
   relationship() between the two — bytes are reached only via an explicit
   `select(ProjectMediaBlob.data)` or `select(func.substring(ProjectMediaBlob.data, ...))`
   in services/project_media_service.py. Adding a relationship here would let a stray
   selectinload/db.refresh pull up to `max_video_size_mb` into a request's session.
2. Hard size caps in core/config.py, enforced *while reading the upload stream*, not
   after (see _read_capped in routers/project_media.py).
3. Video is served by HTTP Range with per-chunk `substring()` reads, so a max-size video
   never exists whole in this process. The migration also does
   `ALTER COLUMN data SET STORAGE EXTERNAL` — with the default EXTENDED (compressed)
   storage, Postgres must decompress the *entire* value to answer a substring(), which
   would defeat the whole design. Video/JPEG/PNG are already compressed, so EXTERNAL
   costs nothing.

UniqueConstraint(project_id, kind) is what makes the upload endpoints an idempotent PUT
(at most one thumbnail + one video per project) instead of an insert that can race. It
must stay in sync with the migration — Base.metadata.create_all (used by the test suite,
tests/conftest.py:63-68) only sees constraints declared here.

user_id is denormalized from projects on purpose: it lets core/ownership.owned() /
require_owned() work with no join like every other table here, and its ON DELETE CASCADE
to users is what makes conftest's `TRUNCATE users ... CASCADE` reach these rows.
"""

import uuid
from enum import StrEnum

from sqlalchemy import BigInteger, Enum, ForeignKey, LargeBinary, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.base import Timestamps, UUIDPk


class MediaKind(StrEnum):
    THUMBNAIL = "thumbnail"
    VIDEO = "video"


class MediaOrigin(StrEnum):
    UPLOADED = "uploaded"
    GENERATED = "generated"


# Shared Enum instances, one per Postgres TYPE — mirrors task_status_enum in
# models/task.py so CREATE TYPE is emitted exactly once by create_all.
media_kind_enum = Enum(MediaKind, name="media_kind")
media_origin_enum = Enum(MediaOrigin, name="media_origin")


class ProjectMedia(Base, UUIDPk, Timestamps):
    __tablename__ = "project_media"
    __table_args__ = (
        UniqueConstraint("project_id", "kind", name="uq_project_media_project_kind"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    kind: Mapped[MediaKind] = mapped_column(media_kind_enum, nullable=False)
    origin: Mapped[MediaOrigin] = mapped_column(
        media_origin_enum, default=MediaOrigin.UPLOADED, nullable=False
    )
    # "image_model" | "svg_poster" for origin=GENERATED, NULL for uploads — lets the UI
    # badge an AI-designed poster card distinctly from a real generated image, and makes
    # the image-model-vs-fallback rate measurable.
    generator: Mapped[str | None] = mapped_column(String(32), nullable=True)

    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(255), nullable=False)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    # Doubles as the HTTP ETag and as the ?v= cache-buster in the URL string returned in
    # ProjectOut — the URL is stable across replaces, so without it a replaced thumbnail
    # keeps showing the old image until a hard reload.
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)


class ProjectMediaBlob(Base):
    """Bytes only. No user_id (reachable only through ProjectMedia, which carries the
    ownership predicate), no timestamps, no relationship back — see ProjectMedia's
    docstring for why the split is structural rather than stylistic."""

    __tablename__ = "project_media_blobs"

    media_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("project_media.id", ondelete="CASCADE"),
        primary_key=True,
    )
    data: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
