"""services/thumbnail_service.py — the context precondition, and run_thumbnail_job's
image-model-first-then-SVG-fallback orchestration, exercised against a stubbed provider
(no real network/API calls; get_provider is patched)."""

from unittest.mock import AsyncMock, patch

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
from app.models.ai_provider_setting import ProviderName
from app.models.extraction_job import JobStatus
from app.models.project import Project
from app.models.project_media import MediaKind, MediaOrigin
from app.models.thumbnail_job import ThumbnailJob
from app.models.user import User
from app.providers.base import GeneratedImage, ProviderError
from app.routers import thumbnails
from app.services import project_media_service, thumbnail_service
from tests.conftest import build_app

# --- has_sufficient_context truth table --------------------------------------------


def test_bare_project_is_insufficient():
    assert not thumbnail_service.has_sufficient_context()


def test_80_plus_chars_of_description_is_sufficient():
    assert thumbnail_service.has_sufficient_context(description_text="x" * 80)


def test_79_chars_of_description_is_not_sufficient():
    assert not thumbnail_service.has_sufficient_context(description_text="x" * 79)


def test_two_technologies_is_sufficient():
    assert thumbnail_service.has_sufficient_context(technologies=["React", "Python"])


def test_one_technology_plus_short_description_is_not_sufficient():
    assert not thumbnail_service.has_sufficient_context(description_text="short", technologies=["React"])


def test_responsibilities_text_alone_counts_too():
    assert thumbnail_service.has_sufficient_context(responsibilities_text="y" * 80)


# --- the router's precondition check -------------------------------------------------


@pytest_asyncio.fixture
async def thumb_client_a(user_a: User):
    app = build_app(thumbnails.router)
    app.dependency_overrides[get_current_user] = lambda: user_a
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client


async def test_generate_on_bare_project_is_422_with_zero_job_rows(
    thumb_client_a, db: AsyncSession, project_a: Project
):
    res = await thumb_client_a.post(f"/api/v1/projects/{project_a.id}/thumbnail/generate", json={})
    assert res.status_code == 422
    assert res.json()["detail"]["code"] == "INSUFFICIENT_PROJECT_CONTEXT"

    from sqlalchemy import select

    jobs = (await db.execute(select(ThumbnailJob).where(ThumbnailJob.project_id == project_a.id))).scalars().all()
    assert jobs == []


async def test_generate_with_sufficient_context_in_request_body_succeeds(
    thumb_client_a, project_a: Project
):
    """project_a itself is bare, but the request body's own context can carry enough —
    covers the create-mode "auto-save then generate with in-form values" path."""
    with patch("app.routers.thumbnails.enqueue_thumbnail", new=AsyncMock()):
        res = await thumb_client_a.post(
            f"/api/v1/projects/{project_a.id}/thumbnail/generate",
            json={"context": {"technologies": ["React", "Python"]}},
        )
    assert res.status_code == 201
    assert "job_id" in res.json()


async def test_other_users_project_generate_is_404(user_b: User, project_a: Project):
    app = build_app(thumbnails.router)
    app.dependency_overrides[get_current_user] = lambda: user_b
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.post(f"/api/v1/projects/{project_a.id}/thumbnail/generate", json={})
    assert res.status_code == 404


# --- run_thumbnail_job orchestration (stubbed provider, no network) -----------------


class _StubProvider:
    def __init__(self, *, image_result=None, image_error=None, poster_result=None, poster_error=None):
        self._image_result = image_result
        self._image_error = image_error
        self._poster_result = poster_result
        self._poster_error = poster_error

    async def generate_image(self, prompt: str, *, aspect_ratio: str = "16:9"):
        if self._image_error:
            raise self._image_error
        return self._image_result

    async def design_poster(self, ctx, json_schema, *, persona):
        if self._poster_error:
            raise self._poster_error
        return self._poster_result

    model = "stub-model"


async def _make_job(db: AsyncSession, project: Project) -> ThumbnailJob:
    job = ThumbnailJob(user_id=project.user_id, project_id=project.id, provider=ProviderName.GEMINI)
    db.add(job)
    await db.commit()
    await db.refresh(job)
    return job


async def test_run_job_succeeds_via_image_model(db: AsyncSession, project_a_rich: Project):
    job = await _make_job(db, project_a_rich)
    stub = _StubProvider(image_result=GeneratedImage(data=b"\x89PNG\r\n\x1a\n" + b"\x00" * 16, mime_type="image/png"))

    with patch("app.services.thumbnail_service.get_provider", new=AsyncMock(return_value=stub)):
        await thumbnail_service.run_thumbnail_job(db, job.id)

    await db.refresh(job)
    assert job.status == JobStatus.SUCCEEDED
    assert job.generator == "image_model"
    media = await project_media_service.get_media(db, project_a_rich.user_id, project_a_rich.id, MediaKind.THUMBNAIL)
    assert media is not None
    assert media.origin == MediaOrigin.GENERATED
    assert media.mime_type == "image/png"


async def test_run_job_falls_back_to_svg_poster_when_image_unsupported(db: AsyncSession, project_a_rich: Project):
    job = await _make_job(db, project_a_rich)
    stub = _StubProvider(
        image_error=ProviderError("IMAGE_GENERATION_UNSUPPORTED", "no image model"),
        poster_result={"palette": ["#112233", "#445566"], "motif": "waves", "headline": "Rich Project"},
    )

    with patch("app.services.thumbnail_service.get_provider", new=AsyncMock(return_value=stub)):
        await thumbnail_service.run_thumbnail_job(db, job.id)

    await db.refresh(job)
    assert job.status == JobStatus.SUCCEEDED
    assert job.generator == "svg_poster"
    media = await project_media_service.get_media(db, project_a_rich.user_id, project_a_rich.id, MediaKind.THUMBNAIL)
    assert media is not None
    assert media.mime_type == "image/svg+xml"
    assert media.origin == MediaOrigin.GENERATED


async def test_run_job_fails_on_auth_error_with_no_silent_fallback(db: AsyncSession, project_a_rich: Project):
    """PROVIDER_AUTH must fail the job outright — falling back to a worse-looking SVG
    would hide a real, actionable problem (an invalid/expired key) from the user."""
    job = await _make_job(db, project_a_rich)
    stub = _StubProvider(image_error=ProviderError("PROVIDER_AUTH", "invalid key"))

    with patch("app.services.thumbnail_service.get_provider", new=AsyncMock(return_value=stub)):
        await thumbnail_service.run_thumbnail_job(db, job.id)

    await db.refresh(job)
    assert job.status == JobStatus.FAILED
    assert job.error_code == "PROVIDER_AUTH"


# No test for run_thumbnail_job's "project is None" branch: thumbnail_jobs.project_id is
# a CASCADE (not SET NULL) foreign key, so a job row can never actually outlive its
# project — deleting the project deletes the job with it in the same transaction,
# unlike breakdown_jobs.document_id (SET NULL), where the analogous check is genuinely
# reachable. The check in thumbnail_service.py stays as defensive belt-and-braces; there
# is no way to construct the state it guards against without violating the schema's own
# FK constraint (attempted and confirmed: inserting a ThumbnailJob with a nonexistent
# project_id raises ForeignKeyViolationError before the row is ever created).


async def test_run_job_rechecks_context_at_run_time(db: AsyncSession, project_a: Project):
    """project_a is bare — even though nothing enforced it at enqueue time in this direct
    call, run_thumbnail_job's own re-check must still catch it."""
    job = await _make_job(db, project_a)
    await thumbnail_service.run_thumbnail_job(db, job.id)
    await db.refresh(job)
    assert job.status == JobStatus.FAILED
    assert job.error_code == "INSUFFICIENT_PROJECT_CONTEXT"
