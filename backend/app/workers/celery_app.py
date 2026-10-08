"""
Background task runner — replaces Celery/Redis.

Uses a standard ThreadPoolExecutor so ML pipeline functions (transcription,
claim extraction, verification, audio deepfake detection) can run without
blocking the FastAPI event loop and without needing an external broker.

Design decisions
----------------
* ThreadPoolExecutor  – Python's GIL is released during CPU-bound torch/ctranslate2
  operations and during IO, so a thread pool is sufficient and avoids the
  serialisation overhead of a subprocess-based queue.
* Job status is tracked directly in PostgreSQL (see AnalysisJob.status) so the
  frontend can poll /api/analyze/{job_id}/status without a Redis dependency.
* If you later need true multi-process workers (e.g. for GPU isolation) you can
  swap this module for a Celery/RQ implementation without touching the API layer.
"""
from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor
from typing import Callable

from app.config import settings

logger = logging.getLogger("fnad.worker")

_executor = ThreadPoolExecutor(
    max_workers=settings.worker_max_threads,
    thread_name_prefix="fnad-worker",
)


def submit_task(fn: Callable, *args, **kwargs):
    """
    Submit a callable to the background thread pool.

    Returns a Future — the caller can ignore it (fire-and-forget) or attach
    a callback via future.add_done_callback(...).
    """
    future = _executor.submit(fn, *args, **kwargs)

    def _log_error(f):
        exc = f.exception()
        if exc:
            logger.error("Background task %s raised an exception: %s", fn.__name__, exc, exc_info=exc)

    future.add_done_callback(_log_error)
    return future


def shutdown(wait: bool = True):
    """Gracefully drain the thread pool on application shutdown."""
    logger.info("Shutting down background thread pool (wait=%s)…", wait)
    _executor.shutdown(wait=wait)
