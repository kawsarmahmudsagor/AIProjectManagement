"""SAQ worker configuration — Postgres backend, no Redis needed on Windows dev
(docs/RESEARCH.md §D). Run with:

    saq app.workers.settings.settings --web

(--web serves SAQ's built-in queue/worker dashboard on :8080, useful for watching a slow
LLM job while developing.)
"""

import asyncio
import sys
from uuid import UUID

from saq import CronJob, Queue

from app import models  # noqa: F401  # registers every ORM model so cross-model
# relationship() string references (e.g. User.chat_sessions -> "ChatSession") resolve —
# this worker process never imports app.main/routers, which is what pulls all model
# modules in transitively on the FastAPI side.
from app.core.config import get_settings
from app.workers import bridge
from app.workers.stale_jobs import reap_stale_jobs
from app.workers.suggestion_refresh import refresh_stale_suggestions
from app.workers.tasks import (
    compact_history,
    generate_session_title,
    recompute_user_suggestions,
    run_extraction_job,
)

if sys.platform == "win32":
    # Only matters for the standalone `saq app.workers.settings.settings` worker CLI,
    # which calls asyncio.new_event_loop() right after importing this module (see
    # saq/worker.py's start()) — that call picks up whatever policy is current, and the
    # worker process never touches Playwright, so Selector is safe (and required, see
    # app/workers/bridge.py) for it. This is a no-op when app/main.py imports this
    # module instead: uvicorn's own loop already exists by then, and changing the
    # policy doesn't affect an already-running loop, only future new_event_loop() calls.
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

_settings = get_settings()


def _to_saq_url(database_url: str) -> str:
    # SAQ's Postgres backend takes a plain postgres:// DSN; our SQLAlchemy URL carries
    # the asyncpg driver suffix, which SAQ doesn't need.
    return database_url.replace("postgresql+asyncpg://", "postgres://")


queue = Queue.from_url(_to_saq_url(_settings.database_url))


async def enqueue_extraction(job_id: UUID) -> None:
    # Called from the FastAPI process, whose main loop is Proactor (for Playwright) —
    # must run on the bridge thread's Selector loop, see app/workers/bridge.py. The SAQ
    # worker process that actually executes the job never calls this function itself,
    # so it isn't affected.
    #
    # timeout=600 matches stale_jobs._STALE_AFTER — SAQ's own default is 10s, far too
    # short for an LLM extraction call (PDF parsing + structured-output generation), and
    # would otherwise cancel the job mid-flight well before the stale-job reaper (which
    # only catches a crashed worker) ever gets a chance to.
    #
    # key=str(job_id) makes the SAQ job's own key match our ExtractionJob.id, so
    # request_cancel below can look it up without a separate id mapping.
    await bridge.run_async(
        queue.enqueue("run_extraction_job", job_id=str(job_id), key=str(job_id), timeout=600)
    )


async def enqueue_generate_title(session_id: UUID) -> None:
    # No `key=` (unlike enqueue_extraction) — nothing needs to look this job up later,
    # and generate_session_title's own "still 'New chat'?" guard makes a duplicate
    # enqueue harmless, so no dedup key is worth the complexity.
    await bridge.run_async(
        queue.enqueue("generate_session_title", session_id=str(session_id), timeout=60)
    )


async def enqueue_compact_history(session_id: UUID) -> None:
    await bridge.run_async(queue.enqueue("compact_history", session_id=str(session_id), timeout=120))


async def enqueue_suggestion_recompute(user_id: UUID) -> None:
    # key=f"user-suggestions:{user_id}" collapses rapid successive project edits for the
    # same user into one queued job (SAQ skips enqueuing a duplicate while a job with this
    # key is already queued/active) — recompute_user_suggestions' own debounce check in
    # suggestion_service.py additionally covers the case where a prior job already ran and
    # completed recently.
    await bridge.run_async(
        queue.enqueue(
            "recompute_user_suggestions",
            user_id=str(user_id),
            key=f"user-suggestions:{user_id}",
            timeout=60,
        )
    )


async def request_cancel(job_id: UUID) -> None:
    """Best-effort: tells the SAQ worker to abort the in-flight task for this job.
    Safe to call even if the job already finished or was never picked up — queue.abort
    on an unknown/terminal key is a no-op (see saq.queue.postgres.Queue.abort). The
    caller (app/routers/jobs.py) is responsible for the ExtractionJob row's own status;
    this only stops the worker from continuing to burn provider calls."""

    async def _abort() -> None:
        job = await queue.job(str(job_id))
        if job is not None:
            await queue.abort(job, "Cancelled by user")

    await bridge.run_async(_abort())


settings = {
    "queue": queue,
    "functions": [
        run_extraction_job,
        generate_session_title,
        compact_history,
        recompute_user_suggestions,
    ],
    "concurrency": _settings.saq_concurrency,
    "cron_jobs": [
        CronJob(reap_stale_jobs, cron="*/5 * * * *"),
        # Every 20 min, not 5 — unlike reap_stale_jobs (a pure DB sweep), this makes real
        # outbound GitHub calls (batched/paced in suggestion_service.py); a tighter
        # interval would eat into the shared rate-limit budget for no user-visible
        # benefit, since suggestions are also individually TTL'd.
        CronJob(refresh_stale_suggestions, cron="*/20 * * * *"),
    ],
}
