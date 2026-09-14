"""HTTP Range support for GET /projects/{id}/video — the highest-risk code in the media
feature (Range arithmetic + a streaming generator that outlives the request's own DB
session). Uses a ~3 MB synthetic video so ranges cross the 1 MiB chunk boundary
(core/config.Settings.media_stream_chunk_bytes), which is what would catch an off-by-one
in the 1-indexed `substring(data from N for L)` call in project_media_service.iter_blob.
"""

from unittest.mock import AsyncMock, patch

import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.core.deps import get_current_user
from app.models.project import Project
from app.models.user import User
from app.routers import project_media
from tests.conftest import build_app

_MP4_HEADER = b"\x00\x00\x00\x18ftypisom"
_SIZE = 3 * 1024 * 1024 + 12345  # deliberately not a round number of chunks
_BODY = bytes((i * 37 + 11) % 256 for i in range(_SIZE - len(_MP4_HEADER)))
_VIDEO_BYTES = _MP4_HEADER + _BODY


@pytest_asyncio.fixture
async def video_client(user_a: User, project_a: Project):
    app = build_app(project_media.router)
    app.dependency_overrides[get_current_user] = lambda: user_a
    # Same convention as test_thumbnail_generation.py: the SAQ bridge loop isn't running
    # in this minimal test app (see tests/conftest.py's build_app docstring), so the
    # real upload_video endpoint's fire-and-forget frame-extraction enqueue is patched
    # out — this file is about Range serving, not frame extraction.
    with patch("app.routers.project_media.enqueue_video_frame_extraction", new=AsyncMock()):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            res = await client.put(
                f"/api/v1/projects/{project_a.id}/video", files={"file": ("v.mp4", _VIDEO_BYTES, "video/mp4")}
            )
            assert res.status_code == 200
            yield client


def _video_url(project_a: Project) -> str:
    return f"/api/v1/projects/{project_a.id}/video"


async def test_no_range_returns_full_body(video_client, project_a: Project):
    res = await video_client.get(_video_url(project_a))
    assert res.status_code == 200
    assert res.headers["accept-ranges"] == "bytes"
    assert int(res.headers["content-length"]) == len(_VIDEO_BYTES)
    assert res.content == _VIDEO_BYTES


async def test_small_range_from_start(video_client, project_a: Project):
    res = await video_client.get(_video_url(project_a), headers={"Range": "bytes=0-1023"})
    assert res.status_code == 206
    assert res.headers["content-range"] == f"bytes 0-1023/{len(_VIDEO_BYTES)}"
    assert res.headers["content-length"] == "1024"
    assert res.content == _VIDEO_BYTES[0:1024]


async def test_open_ended_range(video_client, project_a: Project):
    start = 1000
    res = await video_client.get(_video_url(project_a), headers={"Range": f"bytes={start}-"})
    assert res.status_code == 206
    assert res.content == _VIDEO_BYTES[start:]


async def test_suffix_range_last_n_bytes(video_client, project_a: Project):
    """The suffix form (bytes=-500) is what most players use to fetch the trailing moov
    atom of an MP4 first."""
    res = await video_client.get(_video_url(project_a), headers={"Range": "bytes=-500"})
    assert res.status_code == 206
    assert res.content == _VIDEO_BYTES[-500:]
    assert len(res.content) == 500


async def test_multi_chunk_range_crossing_chunk_boundary(video_client, project_a: Project):
    """This is the test that catches a 1-indexed substring() off-by-one: the range spans
    more than one 1 MiB chunk, so the concatenated stream must equal the exact slice."""
    start, end = 1_048_570, 2_097_162  # crosses the 1 MiB (1_048_576) boundary twice
    res = await video_client.get(_video_url(project_a), headers={"Range": f"bytes={start}-{end}"})
    assert res.status_code == 206
    expected = _VIDEO_BYTES[start : end + 1]
    assert res.content == expected
    assert len(res.content) == end - start + 1


async def test_unsatisfiable_range_is_416(video_client, project_a: Project):
    huge = len(_VIDEO_BYTES) + 1000
    res = await video_client.get(_video_url(project_a), headers={"Range": f"bytes={huge}-"})
    assert res.status_code == 416
    assert res.headers["content-range"] == f"bytes */{len(_VIDEO_BYTES)}"


async def test_malformed_range_falls_back_to_full_body(video_client, project_a: Project):
    """Per RFC 9110 §14.2, a Range header the server doesn't understand is ignored, not
    rejected — pinning that decision."""
    res = await video_client.get(_video_url(project_a), headers={"Range": "items=0-5"})
    assert res.status_code == 200
    assert res.content == _VIDEO_BYTES


async def test_if_none_match_returns_304_with_no_body(video_client, project_a: Project):
    first = await video_client.get(_video_url(project_a))
    etag = first.headers["etag"]
    res = await video_client.get(_video_url(project_a), headers={"If-None-Match": etag})
    assert res.status_code == 304
    assert res.content == b""


async def test_streamed_read_matches_full_content(video_client, project_a: Project):
    """Reads the response by streaming in pieces (client.stream + aiter_bytes) rather
    than the buffered `.content` — a closed-session bug in iter_blob's generator (it must
    open its own async_session_factory() session, not reuse the route's) would only
    surface under this kind of incremental consumption, since httpx's ASGITransport
    drains a StreamingResponse eagerly when you just read `.content`."""
    chunks = []
    async with video_client.stream("GET", _video_url(project_a)) as res:
        assert res.status_code == 200
        async for chunk in res.aiter_bytes():
            chunks.append(chunk)
    assert b"".join(chunks) == _VIDEO_BYTES
