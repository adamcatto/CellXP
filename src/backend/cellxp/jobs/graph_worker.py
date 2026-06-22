"""Dedicated Redis graph executor for production run start/resume/cancel commands."""

from __future__ import annotations

import os
import signal
import socket
from typing import Any

from cellxp.api.runtime import DurableRuntime
from cellxp.config.settings import Settings
from cellxp.jobs.queues import RedisJobQueue
from cellxp.jobs.tasks import GRAPH_CANCEL, GRAPH_RESUME, GRAPH_START
from cellxp.jobs.worker import run_worker


def handlers(runtime: DurableRuntime):  # noqa: ANN201
    def start(payload: dict[str, Any]) -> None:
        runtime.execute_queued(str(payload["run_id"]))

    def resume(payload: dict[str, Any]) -> None:
        runtime.resume_queued(
            str(payload["run_id"]), str(payload["item_id"]), payload["value"],
            str(payload["expected_status"]),
        )

    def cancel(payload: dict[str, Any]) -> None:
        runtime.refresh_run(str(payload["run_id"]))
        runtime.cancel(str(payload["run_id"]))

    return {GRAPH_START: start, GRAPH_RESUME: resume, GRAPH_CANCEL: cancel}


def main() -> None:
    settings = Settings()
    runtime = DurableRuntime(settings.database_url)
    queue = RedisJobQueue.from_url(
        settings.redis_url, stream=settings.graph_job_stream,
        group=settings.graph_consumer_group,
    )
    stopping = False

    def request_stop(signum: int, frame: object) -> None:
        del signum, frame
        nonlocal stopping
        stopping = True

    signal.signal(signal.SIGTERM, request_stop)
    signal.signal(signal.SIGINT, request_stop)
    consumer = os.getenv("GRAPH_EXECUTOR_CONSUMER", socket.gethostname())
    run_worker(queue, handlers(runtime), consumer=consumer, stop=lambda: stopping)


if __name__ == "__main__":
    main()
