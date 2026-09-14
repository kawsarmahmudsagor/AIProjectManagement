"""AI project-thumbnail generation: an image-model call first, falling back to a
deterministic SVG "poster card" (services/poster_renderer.py) when no image model is
available or the call fails. Runs as an async SAQ job (models/thumbnail_job.py) rather
than synchronously — the realistic worst case is two sequential provider calls (an image
attempt, then a text-model poster design) plus rendering, long enough to risk uvicorn's
and the frontend BFF's own timeouts if held open. The precondition check
(has_sufficient_context) is deliberately ALSO run synchronously in the router before a
job row is even created (routers/thumbnails.py) — it's a pure DB predicate with zero LLM
cost, and a job that immediately fails would show a spinner-then-error, strictly worse
than an inline 422. It's re-checked here too, since the project can be edited between
enqueue and run.

Follows the exact status-ladder / _fail / outer-catch-all shape as
breakdown_service.run_breakdown_job — see that module's docstring for the underlying
"a background job's row must always reach a terminal status" rule.
"""

import logging
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.extraction_job import JobStatus
from app.models.project import Project
from app.models.project_media import MediaOrigin, MediaKind
from app.models.thumbnail_job import ThumbnailJob
from app.models.user import AgentPersona, User
from app.providers.base import GeneratedImage, ProviderError, ThumbnailPromptInput
from app.providers.prompts import (
    POSTER_DESIGN_SYSTEM_PROMPT,
    build_poster_design_prompt,
    build_thumbnail_image_prompt,
)
from app.providers.registry import get_provider
from app.providers.schema_utils import inline_refs
from app.schemas.thumbnail import LLMPosterSpec
from app.services import project_media_service
from app.services.poster_renderer import normalize_poster_spec, render_poster_svg

logger = logging.getLogger(__name__)

_POSTER_SCHEMA = inline_refs(LLMPosterSpec.model_json_schema())

# name/role can't be the signal for "is there enough context" — both are NOT NULL with
# min_length=1 (models/project.py, schemas/project.ProjectBase), so the barest possible
# project already has both. Descriptive substance is the actual signal.
_MIN_CONTEXT_CHARS = 80

INSUFFICIENT_CONTEXT_MESSAGE = (
    "There isn't enough information about this project yet to design a thumbnail. "
    "Add a description (or a few technologies) and try again."
)

# Only these codes trigger the SVG fallback — a real auth/rate-limit problem should
# surface as the real problem, not be silently papered over by a worse-looking fallback.
_FALLBACK_CODES = {"IMAGE_GENERATION_UNSUPPORTED", "PROVIDER_BAD_REQUEST", "NOT_FOUND"}


def context_text(name: str, role: str, description_text: str, responsibilities_text: str) -> str:
    return " ".join(t.strip() for t in (description_text, responsibilities_text) if t and t.strip())


def has_sufficient_context(
    *, description_text: str = "", responsibilities_text: str = "", technologies: list[str] | None = None
) -> bool:
    text_len = len(context_text("", "", description_text, responsibilities_text))
    return text_len >= _MIN_CONTEXT_CHARS or bool(technologies and len(technologies) >= 2)


def build_prompt_input_from_project(project: Project) -> ThumbnailPromptInput:
    return ThumbnailPromptInput(
        name=project.name,
        role=project.role,
        technologies=project.technologies,
        description_text=project.description_long_text or project.description_short_text,
        responsibilities_text=project.responsibilities_long_text or project.responsibilities_short_text,
    )


async def _fail(db: AsyncSession, job: ThumbnailJob, code: str, message: str) -> None:
    job.status = JobStatus.FAILED
    job.error_code = code
    job.error_message = message
    job.finished_at = datetime.now(UTC)
    await db.commit()


def _generated_filename(project_name: str, mime_type: str) -> str:
    ext = "svg" if mime_type == "image/svg+xml" else "png"
    safe = "".join(c for c in project_name if c.isalnum() or c in " -_")[:60].strip() or "thumbnail"
    return f"{safe}.{ext}"


async def run_thumbnail_job(db: AsyncSession, job_id: UUID) -> None:
    job = await db.get(ThumbnailJob, job_id)
    if job is None:
        logger.error("thumbnail job %s not found", job_id)
        return

    project = await db.get(Project, job.project_id)
    if project is None or project.user_id != job.user_id:
        await _fail(db, job, "PROJECT_MISSING", "That project no longer exists.")
        return

    # Re-checked even though routers/thumbnails.py already validated this before
    # enqueueing — the project can be edited (or emptied) between enqueue and run.
    if not has_sufficient_context(
        description_text=project.description_long_text or project.description_short_text,
        responsibilities_text=project.responsibilities_long_text or project.responsibilities_short_text,
        technologies=project.technologies,
    ):
        await _fail(db, job, "INSUFFICIENT_PROJECT_CONTEXT", INSUFFICIENT_CONTEXT_MESSAGE)
        return

    job.status = JobStatus.PARSING  # assembling the prompt from the project's own fields
    job.started_at = datetime.now(UTC)
    await db.commit()

    try:
        user = await db.get(User, job.user_id)
        persona = user.agent_persona if user else AgentPersona.BUSINESS_ANALYST
        ctx = build_prompt_input_from_project(project)

        job.status = JobStatus.EXTRACTING  # calling the image model
        await db.commit()

        try:
            provider = await get_provider(db, job.user_id, job.provider, purpose="thumbnail_image")
        except ProviderError as exc:
            await _fail(db, job, exc.code, exc.message)
            return

        generator = "image_model"
        image: GeneratedImage
        try:
            image = await provider.generate_image(build_thumbnail_image_prompt(ctx), aspect_ratio="16:9")
        except ProviderError as exc:
            if exc.code not in _FALLBACK_CODES:
                await _fail(db, job, exc.code, exc.message)
                return
            logger.info("thumbnail job %s falling back to SVG poster (%s)", job_id, exc.code)

            job.status = JobStatus.STRUCTURING  # designing a poster card instead
            await db.commit()

            try:
                poster_provider = await get_provider(db, job.user_id, job.provider, purpose="thumbnail_poster")
                raw = await poster_provider.design_poster(ctx, json_schema=_POSTER_SCHEMA, persona=persona)
            except ProviderError as inner:
                await _fail(db, job, inner.code, inner.message)
                return

            spec = normalize_poster_spec(raw, ctx)  # never raises
            svg = render_poster_svg(spec, seed=str(project.id))
            image = GeneratedImage(data=svg.encode("utf-8"), mime_type="image/svg+xml")
            generator = "svg_poster"

        media = await project_media_service.replace_media(
            db,
            user_id=job.user_id,
            project_id=project.id,
            kind=MediaKind.THUMBNAIL,
            data=image.data,
            mime_type=image.mime_type,
            filename=_generated_filename(project.name, image.mime_type),
            origin=MediaOrigin.GENERATED,
            generator=generator,
        )

        job.media_id = media.id
        job.generator = generator
        job.status = JobStatus.SUCCEEDED
        job.finished_at = datetime.now(UTC)
        await db.commit()
    except Exception:
        # Same reasoning as breakdown_service.run_breakdown_job's catch-all: without
        # this, a bug here leaves the row stuck non-terminal until the stale reaper, and
        # the frontend's poll never ends.
        logger.exception("Unexpected error running thumbnail job %s", job_id)
        await db.rollback()
        await _fail(
            db, job, "UNEXPECTED_ERROR", "Something went wrong while generating the thumbnail. Please try again."
        )
