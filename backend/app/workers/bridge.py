"""Bridges FastAPI's main event loop to SAQ's psycopg-based Postgres queue.

Windows can't give a single asyncio loop both capabilities the app needs at once:
Playwright's driver needs to spawn a subprocess (ProactorEventLoop only — see the
"no --reload on Windows" note in README.md), while psycopg's async mode needs
`loop.add_reader`/`add_writer` (SelectorEventLoop only; Proactor raises "Psycopg cannot
use the 'ProactorEventLoop'"). Since `app/main.py`'s lifespan already commits the main
loop to Proactor for Playwright, the queue (app/workers/settings.py) instead runs on a
dedicated background thread with its own SelectorEventLoop — every coroutine that
touches it must go through `run_async` here, never be awaited directly on the main loop.

The standalone SAQ worker process (`saq app.workers.settings.settings`) doesn't need
this: it never touches Playwright, so app/workers/settings.py sets its event loop
policy to Selector directly instead.
"""

import asyncio
import threading
from collections.abc import Coroutine
from concurrent.futures import Future
from typing import TypeVar

T = TypeVar("T")

_loop: asyncio.AbstractEventLoop | None = None
_thread: threading.Thread | None = None


def _run(ready: threading.Event) -> None:
    global _loop
    loop = asyncio.SelectorEventLoop()
    asyncio.set_event_loop(loop)
    _loop = loop
    ready.set()
    try:
        loop.run_forever()
    finally:
        loop.close()


def start() -> None:
    global _thread
    if _thread is not None:
        return
    ready = threading.Event()
    _thread = threading.Thread(target=_run, args=(ready,), name="saq-selector-loop", daemon=True)
    _thread.start()
    ready.wait()


def stop() -> None:
    global _thread, _loop
    if _loop is None:
        return
    loop = _loop
    loop.call_soon_threadsafe(loop.stop)
    if _thread is not None:
        _thread.join(timeout=5)
    _thread = None
    _loop = None


def run(coro: Coroutine[object, object, T]) -> "Future[T]":
    if _loop is None:
        raise RuntimeError("The SAQ bridge loop isn't running — call bridge.start() first")
    return asyncio.run_coroutine_threadsafe(coro, _loop)


async def run_async(coro: Coroutine[object, object, T]) -> T:
    return await asyncio.wrap_future(run(coro))
