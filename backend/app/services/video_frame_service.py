"""Extracts a handful of still frames from a project's uploaded video, for the project
detail page's read-only carousel (frontend/components/projects/video-frame-carousel.tsx).
This is NOT a new upload feature — there is still exactly one video per project
(models/project_media.py); these frames are a derived, regeneratable-on-replace view of
it, mirroring ProjectMedia/ProjectMediaBlob's bytes-in-their-own-table split (see
models/project_video_frame.py's docstring).

Runs as a background SAQ job (models/video_frame_job.py) triggered right after a video
upload/replace succeeds (routers/project_media.py::upload_video) — decoding and
re-encoding several frames is slow enough to not hold a request open for, and unlike
FAQJob this job has no LLM call at all, just CPU-bound decode/resize/encode work.

Uses PyAV (`av`) rather than opencv-python-headless specifically because av.open() can
decode directly from an in-memory buffer (io.BytesIO) — OpenCV's conventional
bytes-decoding path needs the data written to a temp file first, which would break
models/project_media.py's explicit "video bytes never touch disk" design rationale. Both
ship self-contained wheels with no system ffmpeg binary required.
"""

import hashlib
import io
import logging
from datetime import UTC, datetime
from uuid import UUID

import av
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models.extraction_job import JobStatus
from app.models.project_media import MediaKind, ProjectMedia
from app.models.project_video_frame import ProjectVideoFrame, ProjectVideoFrameBlob
from app.models.video_frame_job import VideoFrameJob
from app.schemas.project_media import ProjectMediaRef
from app.services import project_media_service

logger = logging.getLogger(__name__)

_MIN_DURATION_FOR_TRIM_S = 3.0
_TRIM_LO, _TRIM_HI = 0.05, 0.95


def sample_timestamps(duration_s: float, count: int) -> list[float]:
    """Evenly spaced timestamps (seconds) to grab frames at. Between 5%-95% of duration
    for anything long enough to have a real "middle" — skips likely black/logo intro and
    outro frames. Falls back to a plain 0%-100% even split for very short clips, where
    trimming 10% off each end would cluster every sample within a fraction of a second of
    each other. count=1 returns the midpoint."""
    if count <= 1:
        return [duration_s / 2]
    if duration_s < _MIN_DURATION_FOR_TRIM_S:
        return [duration_s * i / (count - 1) for i in range(count)]
    lo, hi = duration_s * _TRIM_LO, duration_s * _TRIM_HI
    return [lo + (hi - lo) * i / (count - 1) for i in range(count)]


def extract_frames(data: bytes, *, count: int, max_dimension_px: int, jpeg_quality: int) -> list[bytes]:
    """Decodes `data` (an already-validated video byte string) and returns up to `count`
    JPEG-encoded stills, long edge capped at max_dimension_px. Never raises: an
    unreadable container, a duration of zero, or a seek/decode failure on one particular
    timestamp all just mean fewer (possibly zero) frames come back — the caller
    (run_video_frame_job) decides what "zero usable frames" means for the job's terminal
    status, same "repair, don't reject" philosophy services/faq_service.normalize_faq
    applies to LLM output instead of decode failures."""
    try:
        container = av.open(io.BytesIO(data))
    except Exception:
        logger.warning("video_frame_service: could not open container", exc_info=True)
        return []

    try:
        if not container.streams.video:
            return []
        stream = container.streams.video[0]

        duration_s: float | None = None
        if stream.duration is not None and stream.time_base is not None:
            duration_s = float(stream.duration * stream.time_base)
        elif container.duration is not None:
            duration_s = float(container.duration / av.time_base)
        if not duration_s or duration_s <= 0:
            return []

        frames: list[bytes] = []
        for ts in sample_timestamps(duration_s, count):
            try:
                container.seek(int(ts / stream.time_base), stream=stream)
                decoded = next(container.decode(stream), None)
                if decoded is None:
                    continue
                if decoded.width > max_dimension_px or decoded.height > max_dimension_px:
                    scale = max_dimension_px / max(decoded.width, decoded.height)
                    decoded = decoded.reformat(width=max(1, int(decoded.width * scale)), height=max(1, int(decoded.height * scale)))
                image = decoded.to_image().convert("RGB")
                out = io.BytesIO()
                image.save(out, format="JPEG", quality=jpeg_quality)
                frames.append(out.getvalue())
            except Exception:
                # One bad timestamp (a corrupt GOP, a seek past a discontinuity) must not
                # sink the whole job — skip it and keep whatever frames did decode.
                logger.warning("video_frame_service: failed to extract frame at %.2fs", ts, exc_info=True)
                continue
        return frames
    finally:
        container.close()


async def _fail(db: AsyncSession, job: VideoFrameJob, code: str, message: str) -> None:
    job.status = JobStatus.FAILED
    job.error_code = code
    job.error_message = message
    job.finished_at = datetime.now(UTC)
    await db.commit()


async def run_video_frame_job(db: AsyncSession, job_id: UUID) -> None:
    job = await db.get(VideoFrameJob, job_id)
    if job is None:
        logger.error("video frame job %s not found", job_id)
        return

    media = await db.get(ProjectMedia, job.video_media_id) if job.video_media_id else None
    if media is None or media.kind != MediaKind.VIDEO or media.user_id != job.user_id:
        await _fail(db, job, "VIDEO_MISSING", "The uploaded video no longer exists.")
        return

    job.status = JobStatus.PARSING  # reading the video blob
    job.started_at = datetime.now(UTC)
    await db.commit()

    try:
        # Whole-blob read is a deliberate, narrow exception to project_media_service.
        # read_blob's own docstring ("only ever used for the thumbnail path... never for
        # video") — frame decoding fundamentally needs the whole file, unlike the
        # Range-serving HTTP path that invariant protects. Safe here specifically because
        # this runs in the background worker, bounded by saq_concurrency, not per-inbound-
        # HTTP-request concurrency, and is still capped by max_video_size_mb.
        data = await project_media_service.read_blob(db, media.id)

        job.status = JobStatus.EXTRACTING
        await db.commit()

        settings = get_settings()
        frames = extract_frames(
            data,
            count=settings.video_frame_count,
            max_dimension_px=settings.video_frame_max_dimension_px,
            jpeg_quality=settings.video_frame_jpeg_quality,
        )
        if not frames:
            await _fail(db, job, "NO_FRAMES_EXTRACTED", "Could not extract any frames from this video.")
            return

        # Idempotent for a retried/duplicate job targeting the same video.
        existing = (
            await db.execute(select(ProjectVideoFrame).where(ProjectVideoFrame.video_media_id == media.id))
        ).scalars().all()
        for row in existing:
            await db.delete(row)
        await db.flush()

        for i, jpeg_bytes in enumerate(frames):
            frame = ProjectVideoFrame(
                user_id=job.user_id,
                project_id=job.project_id,
                video_media_id=media.id,
                order_index=i,
                mime_type="image/jpeg",
                size_bytes=len(jpeg_bytes),
                sha256=hashlib.sha256(jpeg_bytes).hexdigest(),
            )
            db.add(frame)
            await db.flush()
            db.add(ProjectVideoFrameBlob(frame_id=frame.id, data=jpeg_bytes))

        job.status = JobStatus.SUCCEEDED
        job.finished_at = datetime.now(UTC)
        await db.commit()
    except Exception:
        logger.exception("Unexpected error running video frame job %s", job_id)
        await db.rollback()
        await _fail(db, job, "UNEXPECTED_ERROR", "Something went wrong while processing this video.")


async def frames_by_project(db: AsyncSession, user_id: UUID, project_id: UUID) -> list[ProjectVideoFrame]:
    """Ordered read for one project's detail page — single-project only (like
    faq_service.get_latest_result), since frames only ever render there, never in a
    list."""
    stmt = (
        select(ProjectVideoFrame)
        .where(ProjectVideoFrame.user_id == user_id, ProjectVideoFrame.project_id == project_id)
        .order_by(ProjectVideoFrame.order_index)
    )
    return list((await db.execute(stmt)).scalars().all())


async def read_frame_blob(db: AsyncSession, frame_id: UUID) -> bytes:
    """Frames are small (a few hundred KB JPEG each), so — unlike video — they're always
    read whole, never range-served."""
    stmt = select(ProjectVideoFrameBlob.data).where(ProjectVideoFrameBlob.frame_id == frame_id)
    data = (await db.execute(stmt)).scalar_one_or_none()
    return bytes(data) if data is not None else b""


def frame_ref(project_id: UUID, frame: ProjectVideoFrame) -> ProjectMediaRef:
    """Builds a ProjectMediaRef for one frame — reuses the existing DTO rather than a new
    schema type, since it's already exactly the shape an <img>-rendering carousel needs
    (see schemas/project.py's Project.video_frames)."""
    return ProjectMediaRef(
        url=f"projects/{project_id}/video-frames/{frame.id}?v={frame.sha256[:12]}",
        mime_type=frame.mime_type,
        size_bytes=frame.size_bytes,
        origin="generated",
        generator="video_frame_extraction",
    )
