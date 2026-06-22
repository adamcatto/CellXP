"""N3 detached API-to-graph-executor lifecycle over a durable repository."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from cellxp.api.runtime import DurableRuntime, QueuedRuntime
from cellxp.api.schemas import CreateRunRequest, CreateSessionRequest


class RecordingQueue:
    def __init__(self) -> None:
        self.commands: list[tuple[str, dict[str, Any], str | None]] = []

    def enqueue(
        self, task: str, payload: dict[str, Any], *, job_id: str | None = None,
        **kwargs: Any,
    ) -> str:
        del kwargs
        self.commands.append((task, payload, job_id))
        return job_id or "job"


def runtime(tmp_path: Path) -> QueuedRuntime:
    value = QueuedRuntime.__new__(QueuedRuntime)
    DurableRuntime.__init__(value, f"sqlite:///{tmp_path / 'runtime.db'}")
    value.queue = RecordingQueue()  # type: ignore[assignment]
    return value


def test_api_persists_and_enqueues_without_inline_graph_execution(tmp_path: Path) -> None:
    api = runtime(tmp_path)
    session = api.create_session(CreateSessionRequest(type="general", title="Detached"))
    response = api.create_run(
        session.id,
        CreateRunRequest(
            message="human GRCh38 variant effect", client_request_id="request-1"
        ),
    )

    snapshot = api.get_run(response.run_id)
    assert snapshot["status"] == "queued"
    assert snapshot["steps"] == []
    assert api.queue.commands == [
        (
            "graph.start.v1",
            {"schema_version": "1.0", "run_id": response.run_id},
            f"start:{response.run_id}",
        )
    ]

    # The executor consumes the command against the same durable repository.
    api.execute_queued(response.run_id)
    assert api.get_run(response.run_id)["status"] == "completed"


def test_resume_is_enqueued_and_executor_resumes_checkpoint(tmp_path: Path) -> None:
    api = runtime(tmp_path)
    session = api.create_session(CreateSessionRequest(type="general", title="Detached"))
    response = api.create_run(
        session.id,
        CreateRunRequest(message="smoke", client_request_id="request-2"),
    )
    api.execute_queued(response.run_id)
    paused = api.get_run(response.run_id)
    clarification = paused["pending_clarification"]

    answer = {"selected_option_ids": [], "freeform": "human GRCh38 variant effect"}
    api.resume(response.run_id, clarification["id"], answer, "awaiting_input")
    assert api.get_run(response.run_id)["status"] == "awaiting_input"
    task, payload, _ = api.queue.commands[-1]
    assert task == "graph.resume.v1"

    api.resume_queued(
        response.run_id, clarification["id"], answer, "awaiting_input"
    )
    assert api.get_run(response.run_id)["status"] == "completed"
    assert payload["item_id"] == clarification["id"]
