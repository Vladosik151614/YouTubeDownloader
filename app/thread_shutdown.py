"""Bounded, cooperative shutdown for QThread workers.

Closing a window must never wait indefinitely for a network request or an
external program which ignored a cancellation request.  Workers stay retained
until their native ``finished()`` signal arrives; this helper only bounds how
long the GUI thread waits during shutdown.
"""
from __future__ import annotations

import time
from collections.abc import Iterable

from app.logger import logger


DEFAULT_WAIT_MS = 750


def cancel_and_wait_bounded(
    workers: Iterable,
    *,
    label: str,
    wait_ms: int = DEFAULT_WAIT_MS,
) -> list:
    """Request cancellation and wait at most ``wait_ms`` in total.

    Returning a worker means it is still running.  The caller must retain that
    worker and let its native Qt ``finished()`` signal perform the eventual
    cleanup.  Calling ``QThread.terminate()`` here would be unsafe because the
    workers execute Python and may hold files or Qt objects.
    """
    workers = [worker for worker in workers if worker is not None]
    for worker in workers:
        try:
            cancel = getattr(worker, "cancel", None)
            if callable(cancel):
                cancel()
            else:
                worker.requestInterruption()
        except Exception:
            logger.exception("Unable to request cancellation for %s", label)

    deadline = time.monotonic() + max(0, int(wait_ms)) / 1000
    still_running = []
    for worker in workers:
        if not worker.isRunning():
            continue
        remaining = max(0, int((deadline - time.monotonic()) * 1000))
        if remaining:
            worker.wait(remaining)
        if worker.isRunning():
            still_running.append(worker)

    if still_running and wait_ms:
        logger.warning(
            "Shutdown deferred: %s worker(s) are still stopping for %s; "
            "the window will not wait indefinitely.",
            len(still_running), label,
        )
    return still_running
