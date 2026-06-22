"""Generic Redis worker loop; model-specific handlers are injected by the worker entrypoint."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any

from .queues import RedisJobQueue


def run_worker(
    queue: RedisJobQueue,
    handlers: Mapping[str, Callable[[dict[str, Any]], Any]],
    *,
    consumer: str,
    stop: Callable[[], bool] = lambda: False,
) -> None:
    queue.setup()
    while not stop():
        job = queue.reserve(consumer)
        if job is None:
            job = queue.reclaim(consumer)
            if job is None:
                continue
        handler = handlers.get(job.task)
        if handler is None:
            raise KeyError(f"no handler registered for job task {job.task!r}")
        try:
            handler(job.payload)
        except Exception:
            queue.retry(job)
        else:
            queue.acknowledge(job)
