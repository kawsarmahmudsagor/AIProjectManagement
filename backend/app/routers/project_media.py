"""Project thumbnail/video upload, delete, and serve — PUT (not POST) for upload because
uq_project_media_project_kind (models/project_media.py) guarantees at most one of each
per project, making upload an idempotent replace rather than an insert that can race.
Video is served with HTTP Range support so a browser <video> can seek without pulling the
whole file (see _parse_range and project_media_service.iter_blob).
"""

import asyncio
from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, Request, Response, UploadFile, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.database import get_db
from app.core.deps import CurrentUser
from app.core.ownership import ResourceNotFoundError, require_owned
from app.ingest.media_sniff import UnsupportedMediaFormatError, sniff_image_mime_type, sniff_video_mime_type
from app.models.project import Project
from app.models.project_media import MediaKind, MediaOrigin
from app.models.user import User
from app.models.video_frame_job import VideoFrameJob
from app.schemas.project_media import ProjectMediaRef
from app.services import project_media_service, video_frame_service
from app.services.document_service import UploadTooLargeError
from app.workers.settings import enqueue_video_frame_extraction

router = APIRouter(prefix="/projects", tags=["project-media"])

# The one hard backstop against N * max_video_size_mb resident in this process at once —
# a per-request size cap alone doesn't limit how many uploads can be in flight together.
_video_upload_slots: asyncio.Semaphore | None = None


def _video_semaphore(settings: Settings) -> asyncio.Semaphore:
    global _video_upload_slots
    if _video_upload_slots is None:
        _video_upload_slots = asyncio.Semaphore(settings.max_concurrent_video_uploads)
    return _video_upload_slots


async def _read_capped(file: UploadFile, max_bytes: int, *, label: str) -> bytes:
    """Reads in chunks with a running cap so an oversized body is rejected mid-stream
    rather than after it's fully resident — unlike document_service.save_upload's
    post-hoc `len(data) > max_bytes` check, which must buffer the whole body first. That
    difference matters more here: the video cap is 2x the document cap, and the bytes
    are then copied again into a bytea query parameter."""
    chunks: list[bytes] = []
    total = 0
    while chunk := await file.read(1024 * 1024):
        total += len(chunk)
        if total > max_bytes:
            raise UploadTooLargeError(f"{label} exceeds the {max_bytes // (1024 * 1024)}MB limit")
        chunks.append(chunk)
    return b"".join(chunks)


class _InvalidRange(Exception):
    pass


def _parse_range(header: str | None, size: int) -> tuple[int, int] | None:
    """Returns an inclusive (start, end) byte range, or None to mean "send the whole
    body". Only the single-range forms `bytes=a-b`, `bytes=a-`, and `bytes=-n` are
    handled — multipart/byteranges is legal HTTP but no browser <video> element sends
    it. An unparseable Range is treated as absent (None -> full body, 200), per RFC 9110
    §14.2 ("a server MUST ignore a Range header field that contains a range unit it does
    not understand"); only a well-formed-but-unsatisfiable range raises _InvalidRange
    (-> 416)."""
    if not header or not header.startswith("bytes="):
        return None
    spec = header[len("bytes=") :].split(",")[0].strip()
    start_s, sep, end_s = spec.partition("-")
    if not sep:
        return None
    try:
        if start_s == "":
            if end_s == "":
                return None
            length = int(end_s)
            if length <= 0:
                raise _InvalidRange
            start, end = max(size - length, 0), size - 1
        else:
            start = int(start_s)
            end = int(end_s) if end_s else size - 1
    except ValueError:
        return None
    if start >= size or start > end:
        raise _InvalidRange
    return start, min(end, size - 1)


def _ascii_filename(name: str) -> str:
    return name.encode("ascii", "ignore").decode("ascii") or "file"


def _to_media_ref(project_id: UUID, media) -> ProjectMediaRef:
    ref = project_media_service.media_ref(project_id, media)
    assert ref is not None  # media was just loaded — always non-None here
    return ref


# --------------------------------------------------------------------------- thumbnail


@router.put("/{project_id}/thumbnail", response_model=ProjectMediaRef, status_code=status.HTTP_200_OK)
async def upload_thumbnail(
    project_id: UUID,
    file: UploadFile = File(...),
    user: User = CurrentUser,
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> ProjectMediaRef:
    await require_owned(db, Project, project_id, user.id, resource="Project")
    try:
        data = await _read_capped(file, settings.max_thumbnail_size_mb * 1024 * 1024, label="Thumbnail")
        mime_type = sniff_image_mime_type(data)  # JPEG/PNG/WEBP only — SVG never accepted from an upload
    except UploadTooLargeError as exc:
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, str(exc)) from exc
    except UnsupportedMediaFormatError as exc:
        raise HTTPException(
            status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, {"code": exc.code, "message": exc.message}
        ) from exc

    media = await project_media_service.replace_media(
        db,
        user_id=user.id,
        project_id=project_id,
        kind=MediaKind.THUMBNAIL,
        data=data,
        mime_type=mime_type,
        filename=file.filename or "thumbnail",
        origin=MediaOrigin.UPLOADED,
    )
    return _to_media_ref(project_id, media)


@router.delete("/{project_id}/thumbnail", status_code=status.HTTP_204_NO_CONTENT)
async def delete_thumbnail(project_id: UUID, user: User = CurrentUser, db: AsyncSession = Depends(get_db)) -> None:
    await require_owned(db, Project, project_id, user.id, resource="Project")
    await project_media_service.delete_media(db, user.id, project_id, MediaKind.THUMBNAIL)


@router.get("/{project_id}/thumbnail")
async def get_thumbnail(
    project_id: UUID, request: Request, user: User = CurrentUser, db: AsyncSession = Depends(get_db)
) -> Response:
    await require_owned(db, Project, project_id, user.id, resource="Project")
    media = await project_media_service.get_media(db, user.id, project_id, MediaKind.THUMBNAIL)
    if media is None:
        raise ResourceNotFoundError("Project thumbnail", project_id)

    etag = f'"{media.sha256}"'
    headers = {
        "ETag": etag,
        "Cache-Control": "private, max-age=3600",
        "Content-Disposition": f'inline; filename="{_ascii_filename(media.filename)}"',
        # A generated poster is served as image/svg+xml — safe under our own origin
        # rendered inside <img src> (script-inert), but nosniff+CSP close the direct-
        # navigation case too. User-uploaded SVG is never accepted (see media_sniff.py's
        # docstring) — this header pair is about defense in depth for OUR OWN output,
        # not a substitute for that upload-time rejection.
        "X-Content-Type-Options": "nosniff",
        "Content-Security-Policy": "default-src 'none'; style-src 'unsafe-inline'",
    }
    if request.headers.get("if-none-match") == etag:
        return Response(status_code=304, headers=headers)

    data = await project_media_service.read_blob(db, media.id)
    return Response(content=data, media_type=media.mime_type, headers=headers)


# ------------------------------------------------------------------------------- video


@router.put("/{project_id}/video", response_model=ProjectMediaRef, status_code=status.HTTP_200_OK)
async def upload_video(
    project_id: UUID,
    file: UploadFile = File(...),
    user: User = CurrentUser,
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> ProjectMediaRef:
    await require_owned(db, Project, project_id, user.id, resource="Project")
    async with _video_semaphore(settings):
        try:
            data = await _read_capped(file, settings.max_video_size_mb * 1024 * 1024, label="Video")
            mime_type = sniff_video_mime_type(data)
        except UploadTooLargeError as exc:
            raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, str(exc)) from exc
        except UnsupportedMediaFormatError as exc:
            raise HTTPException(
                status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, {"code": exc.code, "message": exc.message}
            ) from exc

        media = await project_media_service.replace_media(
            db,
            user_id=user.id,
            project_id=project_id,
            kind=MediaKind.VIDEO,
            data=data,
            mime_type=mime_type,
            filename=file.filename or "video",
            origin=MediaOrigin.UPLOADED,
        )

        # Fire-and-forget frame extraction for the read-only detail-page carousel — see
        # services/video_frame_service.py. replace_media's delete-then-insert means the
        # old video's ProjectVideoFrame rows already cascaded away via video_media_id's
        # ON DELETE CASCADE (models/project_video_frame.py), so there's nothing to clean
        # up here beyond kicking off the new job.
        frame_job = VideoFrameJob(user_id=user.id, project_id=project_id, video_media_id=media.id)
        db.add(frame_job)
        await db.commit()
        await enqueue_video_frame_extraction(frame_job.id)
    return _to_media_ref(project_id, media)


@router.delete("/{project_id}/video", status_code=status.HTTP_204_NO_CONTENT)
async def delete_video(project_id: UUID, user: User = CurrentUser, db: AsyncSession = Depends(get_db)) -> None:
    await require_owned(db, Project, project_id, user.id, resource="Project")
    await project_media_service.delete_media(db, user.id, project_id, MediaKind.VIDEO)


@router.get("/{project_id}/video")
async def get_video(
    project_id: UUID,
    request: Request,
    user: User = CurrentUser,
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> Response:
    """Range-capable so a browser <video> can seek. Deliberately streamed in chunks even
    for a full-body 200 — `select(data)` on a large video would put the whole thing in
    this process's memory, which no upload-time cap protects against once it's already
    stored. NOTE for whoever adds compression middleware later: this route (like
    routers/chat.py's text/event-stream) must be excluded — gzip on a 206 invalidates the
    Content-Range/Content-Length accounting, and re-compressing an already-compressed
    video is pure wasted CPU. app/main.py has no such middleware today."""
    await require_owned(db, Project, project_id, user.id, resource="Project")
    media = await project_media_service.get_media(db, user.id, project_id, MediaKind.VIDEO)
    if media is None:
        raise ResourceNotFoundError("Project video", project_id)

    size = media.size_bytes
    etag = f'"{media.sha256}"'
    headers = {
        "Accept-Ranges": "bytes",
        "ETag": etag,
        "Cache-Control": "private, max-age=3600",
        "Content-Disposition": f'inline; filename="{_ascii_filename(media.filename)}"',
    }
    if request.headers.get("if-none-match") == etag:
        return Response(status_code=304, headers=headers)

    try:
        rng = _parse_range(request.headers.get("range"), size)
    except _InvalidRange:
        return Response(status_code=416, headers={**headers, "Content-Range": f"bytes */{size}"})

    start, end = rng if rng is not None else (0, size - 1)
    status_code = 206 if rng is not None else 200
    if rng is not None:
        headers["Content-Range"] = f"bytes {start}-{end}/{size}"

    return StreamingResponse(
        project_media_service.iter_blob(media.id, start, end, chunk_bytes=settings.media_stream_chunk_bytes),
        status_code=status_code,
        media_type=media.mime_type,
        headers={**headers, "Content-Length": str(end - start + 1)},
    )


# ---------------------------------------------------------------------- video frames


@router.get("/{project_id}/video-frames/{frame_id}")
async def get_video_frame(
    project_id: UUID, frame_id: UUID, request: Request, user: User = CurrentUser, db: AsyncSession = Depends(get_db)
) -> Response:
    """Serves one extracted video-frame still (see services/video_frame_service.py).
    Routed by the frame's own id, not its order_index, so re-running extraction after a
    video replace never creates ambiguity about which bytes an old cached URL points to.
    Frames are always JPEG and small, so — unlike get_video — this is a plain whole-body
    response with no Range support, mirroring get_thumbnail's header shape exactly."""
    await require_owned(db, Project, project_id, user.id, resource="Project")
    frames = await video_frame_service.frames_by_project(db, user.id, project_id)
    frame = next((f for f in frames if f.id == frame_id), None)
    if frame is None:
        raise ResourceNotFoundError("Video frame", frame_id)

    etag = f'"{frame.sha256}"'
    headers = {
        "ETag": etag,
        "Cache-Control": "private, max-age=3600",
        "Content-Disposition": "inline",
        "X-Content-Type-Options": "nosniff",
    }
    if request.headers.get("if-none-match") == etag:
        return Response(status_code=304, headers=headers)

    data = await video_frame_service.read_frame_blob(db, frame.id)
    return Response(content=data, media_type=frame.mime_type, headers=headers)
