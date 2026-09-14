"""Project thumbnail/video storage — bytes as Postgres bytea, split across two tables
(ProjectMedia = metadata, ProjectMediaBlob = bytes) per models/project_media.py's
docstring. The one rule every function here upholds: bytes are read via an explicit
`select(ProjectMediaBlob.data)` or `select(func.substring(...))`, never through a
relationship, so a stray `db.refresh()`/eager-load elsewhere in the app can never pull a
video's bytes into a session that didn't ask for them.
"""

import hashlib
from collections.abc import AsyncIterator
from typing import Sequence
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import async_session_factory
from app.core.ownership import owned
from app.models.project_media import MediaKind, MediaOrigin, ProjectMedia, ProjectMediaBlob
from app.schemas.project_media import ProjectMediaRef


async def replace_media(
    db: AsyncSession,
    *,
    user_id: UUID,
    project_id: UUID,
    kind: MediaKind,
    data: bytes,
    mime_type: str,
    filename: str,
    origin: MediaOrigin,
    generator: str | None = None,
) -> ProjectMedia:
    """Delete-then-insert rather than UPDATE: the blob lives in a separate table, so an
    UPDATE would already be two statements that must agree with each other; a fresh id
    also makes any client still holding the old ETag/`?v=` miss cleanly instead of
    serving stale bytes under a URL that looks unchanged.
    uq_project_media_project_kind guarantees there was at most one row to delete."""
    existing = (
        await db.execute(
            owned(ProjectMedia, user_id).where(
                ProjectMedia.project_id == project_id, ProjectMedia.kind == kind
            )
        )
    ).scalar_one_or_none()
    if existing is not None:
        await db.delete(existing)
        await db.flush()

    media = ProjectMedia(
        user_id=user_id,
        project_id=project_id,
        kind=kind,
        origin=origin,
        generator=generator,
        filename=filename[:255],
        mime_type=mime_type,
        size_bytes=len(data),
        sha256=hashlib.sha256(data).hexdigest(),
    )
    db.add(media)
    await db.flush()
    db.add(ProjectMediaBlob(media_id=media.id, data=data))
    await db.commit()
    await db.refresh(media)  # safe: ProjectMedia itself has no bytes column
    return media


async def get_media(db: AsyncSession, user_id: UUID, project_id: UUID, kind: MediaKind) -> ProjectMedia | None:
    stmt = owned(ProjectMedia, user_id).where(ProjectMedia.project_id == project_id, ProjectMedia.kind == kind)
    return (await db.execute(stmt)).scalar_one_or_none()


async def delete_media(db: AsyncSession, user_id: UUID, project_id: UUID, kind: MediaKind) -> bool:
    """Idempotent — returns whether a row existed, but callers should 204 either way
    (deleting something already gone is not an error; see core/ownership.py's docstring
    on why "doesn't exist" and "already handled" are deliberately indistinguishable)."""
    media = await get_media(db, user_id, project_id, kind)
    if media is None:
        return False
    await db.delete(media)
    await db.commit()
    return True


async def read_blob(db: AsyncSession, media_id: UUID) -> bytes:
    """One read, whole value — only ever used for the thumbnail path (capped at
    max_thumbnail_size_mb), never for video."""
    stmt = select(ProjectMediaBlob.data).where(ProjectMediaBlob.media_id == media_id)
    data = (await db.execute(stmt)).scalar_one_or_none()
    return bytes(data) if data is not None else b""


async def iter_blob(media_id: UUID, start: int, end: int, *, chunk_bytes: int) -> AsyncIterator[bytes]:
    """Yields the inclusive [start, end] byte range in chunk_bytes-sized pieces, one
    `substring(data from N for L)` SELECT per piece — never `select(ProjectMediaBlob.data)`,
    which would materialize the whole value (up to max_video_size_mb) in this process at
    once, exactly the risk the bytea-storage decision carries.

    Opens its OWN session via async_session_factory rather than accepting the caller's:
    this generator keeps running after the route function has already returned, while
    the StreamingResponse body is being sent — a `Depends(get_db)` session's lifetime is
    not guaranteed to outlive that. `substring` is 1-indexed in Postgres, hence `+ 1`.
    """
    offset = start
    async with async_session_factory() as db:
        while offset <= end:
            length = min(chunk_bytes, end - offset + 1)
            stmt = select(func.substring(ProjectMediaBlob.data, offset + 1, length)).where(
                ProjectMediaBlob.media_id == media_id
            )
            piece = (await db.execute(stmt)).scalar_one_or_none()
            if not piece:
                return  # row vanished mid-stream (concurrent delete) — end the stream
            piece_bytes = bytes(piece)
            yield piece_bytes
            offset += len(piece_bytes)


async def media_by_project(
    db: AsyncSession, user_id: UUID, project_ids: Sequence[UUID]
) -> dict[UUID, dict[MediaKind, ProjectMedia]]:
    """One query for a whole page/list — the metadata table only, never the blobs."""
    if not project_ids:
        return {}
    stmt = owned(ProjectMedia, user_id).where(ProjectMedia.project_id.in_(project_ids))
    out: dict[UUID, dict[MediaKind, ProjectMedia]] = {}
    for m in (await db.execute(stmt)).scalars().all():
        out.setdefault(m.project_id, {})[m.kind] = m
    return out


def media_ref(project_id: UUID, media: ProjectMedia | None) -> ProjectMediaRef | None:
    if media is None:
        return None
    path = "thumbnail" if media.kind == MediaKind.THUMBNAIL else "video"
    return ProjectMediaRef(
        url=f"projects/{project_id}/{path}?v={media.sha256[:12]}",
        mime_type=media.mime_type,
        size_bytes=media.size_bytes,
        origin=media.origin.value,
        generator=media.generator,
    )
