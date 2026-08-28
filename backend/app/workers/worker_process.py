"""Auto-starts the SAQ worker as a genuine child process when the FastAPI app boots, so
a separate `saq app.workers.settings.settings` terminal isn't required for local dev.

This has to be a real OS process, not a thread on this app's own loop (tried first,
reverted): the worker's task functions (app/workers/tasks.py) open a DB session through
this app's own SQLAlchemy engine, whose asyncpg connections bind to whichever event loop
first used them — this process's main Proactor loop, from ordinary HTTP request
handling. Running the worker on a second thread's Selector loop broke as soon as a task
touched that engine ("Future attached to a different loop") — asyncpg connections can't
be reused across event loops, even from a different thread. A separate process sidesteps
that entirely: its own interpreter, its own engine, its own loop. The main loop can spawn
it because it's already Proactor for Playwright, which is exactly what subprocess
creation needs.

Running the standalone `saq ... --web` CLI *in addition* to this is still supported and
harmless — SAQ workers claim jobs atomically, so two workers just means jobs get picked
up faster. The dashboard (--web, port 8080) is the only reason to still run it manually.
"""

import asyncio
import logging
import sys
from pathlib import Path

logger = logging.getLogger(__name__)

# app/workers/worker_process.py -> app/workers -> app -> backend/
_BACKEND_DIR = Path(__file__).resolve().parent.parent.parent

_process: "asyncio.subprocess.Process | None" = None
_watch_task: "asyncio.Task[None] | None" = None


async def _watch(process: "asyncio.subprocess.Process") -> None:
    returncode = await process.wait()
    # Not reached on a clean stop() — that cancels this task before the process exits.
    logger.error("Auto-started SAQ worker process exited unexpectedly (code %s)", returncode)


async def start() -> None:
    global _process, _watch_task
    if _process is not None:
        return
    _process = await asyncio.create_subprocess_exec(
        sys.executable, "-m", "saq", "app.workers.settings.settings", cwd=str(_BACKEND_DIR)
    )
    _watch_task = asyncio.create_task(_watch(_process))


async def stop() -> None:
    global _process, _watch_task
    if _process is None:
        return
    if _watch_task is not None:
        _watch_task.cancel()
    # terminate() is a hard TerminateProcess() on Windows (no graceful SIGTERM
    # equivalent without console process-group signaling) — acceptable for a local-dev
    # convenience process; an in-flight job just stays stuck and gets picked up again by
    # whichever worker starts next, same as killing a manually-run worker terminal.
    _process.terminate()
    try:
        await asyncio.wait_for(_process.wait(), timeout=5)
    except asyncio.TimeoutError:
        _process.kill()
        await _process.wait()
    _process = None
    _watch_task = None
