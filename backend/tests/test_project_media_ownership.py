"""Cross-user 404 (never 403, per core/ownership.py's docstring) and no-auth 401 checks
for the project media endpoints — same reasoning as test_task_ownership.py. Builds its
own app via conftest.build_app() rather than the shared _build_app() (which only wires
the task routers).
"""

import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.core.deps import get_current_user
from app.models.project import Project
from app.models.user import User
from app.routers import project_media
from tests.conftest import build_app


def _app():
    return build_app(project_media.router)


@pytest_asyncio.fixture
async def media_client_a(user_a: User):
    app = _app()
    app.dependency_overrides[get_current_user] = lambda: user_a
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client


@pytest_asyncio.fixture
async def media_client_b(user_b: User):
    app = _app()
    app.dependency_overrides[get_current_user] = lambda: user_b
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client


@pytest_asyncio.fixture
async def media_client_no_auth():
    app = _app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client


_PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32


async def test_get_thumbnail_on_project_with_none_is_404(media_client_a, project_a: Project):
    res = await media_client_a.get(f"/api/v1/projects/{project_a.id}/thumbnail")
    assert res.status_code == 404


async def test_upload_thumbnail_then_get_succeeds(media_client_a, project_a: Project):
    res = await media_client_a.put(
        f"/api/v1/projects/{project_a.id}/thumbnail", files={"file": ("t.png", _PNG, "image/png")}
    )
    assert res.status_code == 200
    assert res.json()["mime_type"] == "image/png"

    res = await media_client_a.get(f"/api/v1/projects/{project_a.id}/thumbnail")
    assert res.status_code == 200
    assert res.content == _PNG


async def test_other_users_project_thumbnail_upload_is_404_not_403(media_client_b, project_a: Project):
    """project_a belongs to user_a; client_b (authenticated as user_b) must get 404, the
    same as if the project didn't exist — never 403, which would leak that the id is
    real (core/ownership.py's docstring)."""
    res = await media_client_b.put(
        f"/api/v1/projects/{project_a.id}/thumbnail", files={"file": ("t.png", _PNG, "image/png")}
    )
    assert res.status_code == 404


async def test_other_users_project_thumbnail_get_is_404(media_client_a, media_client_b, project_a: Project):
    await media_client_a.put(f"/api/v1/projects/{project_a.id}/thumbnail", files={"file": ("t.png", _PNG, "image/png")})
    res = await media_client_b.get(f"/api/v1/projects/{project_a.id}/thumbnail")
    assert res.status_code == 404


async def test_other_users_project_thumbnail_delete_is_404(media_client_b, project_a: Project):
    res = await media_client_b.delete(f"/api/v1/projects/{project_a.id}/thumbnail")
    assert res.status_code == 404


async def test_delete_is_idempotent_204_even_with_nothing_to_delete(media_client_a, project_a: Project):
    res = await media_client_a.delete(f"/api/v1/projects/{project_a.id}/thumbnail")
    assert res.status_code == 204


async def test_no_auth_thumbnail_get_is_401(media_client_no_auth, project_a: Project):
    res = await media_client_no_auth.get(f"/api/v1/projects/{project_a.id}/thumbnail")
    assert res.status_code == 401


async def test_no_auth_thumbnail_put_is_401(media_client_no_auth, project_a: Project):
    res = await media_client_no_auth.put(
        f"/api/v1/projects/{project_a.id}/thumbnail", files={"file": ("t.png", _PNG, "image/png")}
    )
    assert res.status_code == 401


async def test_no_auth_thumbnail_delete_is_401(media_client_no_auth, project_a: Project):
    res = await media_client_no_auth.delete(f"/api/v1/projects/{project_a.id}/thumbnail")
    assert res.status_code == 401


async def test_no_auth_video_get_is_401(media_client_no_auth, project_a: Project):
    res = await media_client_no_auth.get(f"/api/v1/projects/{project_a.id}/video")
    assert res.status_code == 401


async def test_get_video_on_project_with_none_is_404(media_client_a, project_a: Project):
    res = await media_client_a.get(f"/api/v1/projects/{project_a.id}/video")
    assert res.status_code == 404
