"""Cross-user 404 checks for the brag-document job/export endpoints — same reasoning as
test_task_ownership.py. Builds its own minimal FastAPI app (conftest.py's shared
_build_app() only wires the tasks routers) and creates BragDocumentJob rows directly via
the `db` fixture rather than through POST /brag-documents, which enqueues a real SAQ job
(app/workers/settings.py's enqueue_brag_document) that would raise "the SAQ bridge loop
isn't running" outside of app.main's lifespan — the same reason test_breakdown_accept.py
never calls the breakdown-creation endpoint over HTTP either.
"""

import pytest_asyncio
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from httpx import ASGITransport, AsyncClient

from app.core.deps import get_current_user
from app.core.ownership import ResourceNotFoundError
from app.models.ai_provider_setting import ProviderName
from app.models.brag_document_job import BragDocumentJob
from app.models.document import Document
from app.models.extraction_job import JobStatus
from app.models.user import User
from app.routers import brag_documents


def _build_app() -> FastAPI:
    app = FastAPI()
    app.include_router(brag_documents.router, prefix="/api/v1")
    app.include_router(brag_documents.brag_document_jobs_router, prefix="/api/v1")

    @app.exception_handler(ResourceNotFoundError)
    async def _not_found(request, exc: ResourceNotFoundError) -> JSONResponse:
        return JSONResponse(status_code=404, content={"detail": f"{exc.resource} not found"})

    return app


@pytest_asyncio.fixture
async def brag_client_a(user_a: User):
    app = _build_app()
    app.dependency_overrides[get_current_user] = lambda: user_a
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client


@pytest_asyncio.fixture
async def brag_client_b(user_b: User):
    app = _build_app()
    app.dependency_overrides[get_current_user] = lambda: user_b
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client


async def _make_document(db, user: User) -> Document:
    doc = Document(
        user_id=user.id,
        filename="standup.xlsx",
        storage_path="/tmp/does-not-matter.xlsx",
        mime_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        size_bytes=10,
        sha256="0" * 64,
    )
    db.add(doc)
    await db.commit()
    await db.refresh(doc)
    return doc


async def _make_job(db, user: User, document: Document, **overrides) -> BragDocumentJob:
    job = BragDocumentJob(
        user_id=user.id,
        document_id=document.id,
        provider=ProviderName.GEMINI,
        name="August 2026 Brag Document",
        member_name="Test Member",
        target_month="August 2026",
        **overrides,
    )
    db.add(job)
    await db.commit()
    await db.refresh(job)
    return job


async def test_cross_user_get_job_is_404(db, user_a: User, brag_client_b: AsyncClient):
    document = await _make_document(db, user_a)
    job = await _make_job(db, user_a, document)

    resp = await brag_client_b.get(f"/api/v1/brag-document-jobs/{job.id}")
    assert resp.status_code == 404


async def test_cross_user_cancel_is_404_and_leaves_job_untouched(db, user_a: User, brag_client_b: AsyncClient):
    document = await _make_document(db, user_a)
    job = await _make_job(db, user_a, document, status=JobStatus.QUEUED)

    resp = await brag_client_b.post(f"/api/v1/brag-document-jobs/{job.id}/cancel")
    assert resp.status_code == 404

    await db.refresh(job)
    assert job.status == JobStatus.QUEUED


async def test_cross_user_export_is_404(db, user_a: User, brag_client_b: AsyncClient):
    document = await _make_document(db, user_a)
    job = await _make_job(db, user_a, document, status=JobStatus.SUCCEEDED, result={}, hour_stats={})

    resp = await brag_client_b.get(f"/api/v1/brag-document-jobs/{job.id}/export?format=docx")
    assert resp.status_code == 404


async def test_owner_can_get_job(db, user_a: User, brag_client_a: AsyncClient):
    document = await _make_document(db, user_a)
    job = await _make_job(db, user_a, document)

    resp = await brag_client_a.get(f"/api/v1/brag-document-jobs/{job.id}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["member_name"] == "Test Member"
    assert body["document_id"] == str(document.id)


async def test_owner_can_export_docx_for_a_succeeded_job(db, user_a: User, brag_client_a: AsyncClient):
    document = await _make_document(db, user_a)
    job = await _make_job(
        db,
        user_a,
        document,
        status=JobStatus.SUCCEEDED,
        result={"technical_contributions": [], "team_support_bullets": [], "learning_bullets": []},
        hour_stats={
            "member_name": "Test Member",
            "month_name": "August",
            "year": 2026,
            "included_weeks": [],
            "total_hours": 40.0,
            "expected_target_hours": 40.0,
            "gross_base_hours": 40.0,
            "holiday_deducted_hours": 0.0,
            "holiday_count": 0,
            "holiday_names": [],
            "leave_count": 0,
            "leave_hours": 0.0,
            "leave_dates": [],
            "blocker_count": 0,
            "billable_hours": 40.0,
            "non_billable_hours": 0.0,
            "balance_hours": 0.0,
            "target_completion_pct": 100.0,
        },
    )

    resp = await brag_client_a.get(f"/api/v1/brag-document-jobs/{job.id}/export?format=docx")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith(
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )
    assert len(resp.content) > 0


async def test_export_before_job_succeeded_is_409(db, user_a: User, brag_client_a: AsyncClient):
    document = await _make_document(db, user_a)
    job = await _make_job(db, user_a, document, status=JobStatus.EXTRACTING)

    resp = await brag_client_a.get(f"/api/v1/brag-document-jobs/{job.id}/export?format=docx")
    assert resp.status_code == 409


async def test_create_against_another_users_document_is_404(db, user_a: User, brag_client_b: AsyncClient):
    document = await _make_document(db, user_a)

    resp = await brag_client_b.post(
        "/api/v1/brag-documents",
        json={"document_id": str(document.id), "member_name": "Test Member", "target_month": "August 2026"},
    )
    assert resp.status_code == 404
