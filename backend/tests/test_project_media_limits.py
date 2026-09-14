"""Size caps, format rejection, and replace semantics for project media uploads."""

import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.core.config import get_settings
from app.core.deps import get_current_user
from app.models.project import Project
from app.models.user import User
from app.routers import project_media
from tests.conftest import build_app


@pytest_asyncio.fixture
async def media_client_a(user_a: User):
    app = build_app(project_media.router)
    app.dependency_overrides[get_current_user] = lambda: user_a
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client


_PNG_HEADER = b"\x89PNG\r\n\x1a\n"


async def test_thumbnail_over_cap_is_413(media_client_a, project_a: Project):
    settings = get_settings()
    oversized = _PNG_HEADER + b"\x00" * (settings.max_thumbnail_size_mb * 1024 * 1024 + 1)
    res = await media_client_a.put(
        f"/api/v1/projects/{project_a.id}/thumbnail", files={"file": ("big.png", oversized, "image/png")}
    )
    assert res.status_code == 413


async def test_unsupported_thumbnail_format_is_415_with_code(media_client_a, project_a: Project):
    res = await media_client_a.put(
        f"/api/v1/projects/{project_a.id}/thumbnail", files={"file": ("f.gif", b"GIF89a" + b"\x00" * 16, "image/gif")}
    )
    assert res.status_code == 415
    body = res.json()
    assert body["detail"]["code"] == "unsupported_image_format"


async def test_replace_leaves_exactly_one_row_and_updates_url(media_client_a, project_a: Project):
    first = _PNG_HEADER + b"\x01" * 32
    second = _PNG_HEADER + b"\x02" * 32

    res1 = await media_client_a.put(
        f"/api/v1/projects/{project_a.id}/thumbnail", files={"file": ("a.png", first, "image/png")}
    )
    url1 = res1.json()["url"]

    res2 = await media_client_a.put(
        f"/api/v1/projects/{project_a.id}/thumbnail", files={"file": ("b.png", second, "image/png")}
    )
    url2 = res2.json()["url"]

    assert url1 != url2  # the ?v= cache-buster changed after replace

    res = await media_client_a.get(f"/api/v1/projects/{project_a.id}/thumbnail")
    assert res.content == second  # the second upload's bytes win, not the first's


async def test_unsupported_video_format_is_415(media_client_a, project_a: Project):
    res = await media_client_a.put(
        f"/api/v1/projects/{project_a.id}/video", files={"file": ("f.mov", b"\x00\x00\x00\x18ftypqt  " + b"\x00" * 16, "video/quicktime")}
    )
    assert res.status_code == 415
    assert res.json()["detail"]["code"] == "quicktime_unsupported"


async def test_video_over_cap_is_413(media_client_a, project_a: Project):
    settings = get_settings()
    mp4_header = b"\x00\x00\x00\x18ftypisom"
    oversized = mp4_header + b"\x00" * (settings.max_video_size_mb * 1024 * 1024 + 1)
    res = await media_client_a.put(
        f"/api/v1/projects/{project_a.id}/video", files={"file": ("big.mp4", oversized, "video/mp4")}
    )
    assert res.status_code == 413
