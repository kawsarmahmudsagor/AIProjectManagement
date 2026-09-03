from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from playwright.async_api import async_playwright

from app.core.config import get_settings
from app.core.ownership import ResourceNotFoundError
from app.routers import (
    ai,
    ai_settings,
    auth,
    brag_documents,
    breakdown,
    chat,
    documents,
    export,
    jobs,
    profile,
    projects,
    suggestions,
    tasks,
)
from app.services.task_service import TaskValidationError
from app.workers import bridge, worker_process
from app.workers.settings import queue as extraction_queue

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # One Chromium instance, reused across every PDF export request — cold-launching
    # Chromium per export is what makes Playwright look slow (backend/DESIGN.md §7).
    playwright = await async_playwright().start()
    app.state.browser = await playwright.chromium.launch()

    # The SAQ worker process opens its own copy of this pool on its own startup; this
    # FastAPI process holds a separate Queue instance (same DB, different process) and
    # calls queue.enqueue() directly from the upload endpoint, so it must open its own
    # pool too — psycopg_pool defaults to closed until connect() is called explicitly.
    # That connect (and every later enqueue) has to happen on the bridge thread's
    # Selector loop, not this process's main Proactor loop — see app/workers/bridge.py.
    bridge.start()
    await bridge.run_async(extraction_queue.connect())

    # Auto-starts the SAQ worker as a child process (app/workers/worker_process.py) so a
    # separate `saq ...` terminal isn't required for local dev — see its docstring for
    # why this has to be a real process rather than an in-process thread, and for why
    # it's safe to also run a standalone worker alongside it if you want SAQ's --web
    # dashboard.
    await worker_process.start()

    try:
        yield
    finally:
        await worker_process.stop()
        await bridge.run_async(extraction_queue.disconnect())
        bridge.stop()
        await app.state.browser.close()
        await playwright.stop()


app = FastAPI(title="AI Project Management Platform API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(ResourceNotFoundError)
async def _resource_not_found_handler(request: Request, exc: ResourceNotFoundError) -> JSONResponse:
    return JSONResponse(status_code=404, content={"detail": f"{exc.resource} not found"})


@app.exception_handler(TaskValidationError)
async def _task_validation_handler(request: Request, exc: TaskValidationError) -> JSONResponse:
    return JSONResponse(status_code=422, content={"detail": str(exc)})


app.include_router(auth.router, prefix="/api/v1")
app.include_router(projects.router, prefix="/api/v1")
app.include_router(documents.router, prefix="/api/v1")
app.include_router(jobs.router, prefix="/api/v1")
app.include_router(ai.router, prefix="/api/v1")
app.include_router(ai_settings.router, prefix="/api/v1")
app.include_router(export.router, prefix="/api/v1")
app.include_router(chat.router, prefix="/api/v1")
app.include_router(profile.router, prefix="/api/v1")
app.include_router(suggestions.router, prefix="/api/v1")
app.include_router(tasks.router, prefix="/api/v1")
app.include_router(tasks.tasks_router, prefix="/api/v1")
app.include_router(breakdown.router, prefix="/api/v1")
app.include_router(breakdown.breakdown_jobs_router, prefix="/api/v1")
app.include_router(brag_documents.router, prefix="/api/v1")
app.include_router(brag_documents.brag_document_jobs_router, prefix="/api/v1")


@app.get("/healthz", tags=["meta"])
async def healthz() -> dict:
    return {"status": "ok"}
