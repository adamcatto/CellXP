"""AG-UI contract coverage for CopilotKit's CellXP adapter."""

from __future__ import annotations

import json

import pytest
from ag_ui.core import RunAgentInput
from cellxp.api.ag_ui import project_state, snapshot_events
from cellxp.api.main import app
from cellxp.api.runtime import runtime
from fastapi.testclient import TestClient

pytestmark = pytest.mark.contract


@pytest.fixture(autouse=True)
def clean_runtime():
    runtime.reset()
    yield
    runtime.reset()


def _session(client: TestClient, title: str = "Copilot workspace") -> str:
    response = client.post(
        "/api/v1/sessions",
        json={
            "type": "general",
            "title": title,
            "defaults": {"organism": "human", "assembly": "GRCh38"},
        },
    )
    assert response.status_code == 201
    return response.json()["id"]


def _input(
    session_id: str,
    ag_ui_run_id: str,
    *,
    message: str = "What does rs699 do?",
    state: dict | None = None,
    resume: list[dict] | None = None,
) -> dict:
    payload = {
        "threadId": session_id,
        "runId": ag_ui_run_id,
        "state": state or {},
        "messages": [{"id": f"user:{ag_ui_run_id}", "role": "user", "content": message}],
        "tools": [],
        "context": [],
        "forwardedProps": {},
    }
    if resume is not None:
        payload["resume"] = resume
    return payload


def _events(response) -> list[dict]:
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    return [
        json.loads(line.removeprefix("data: "))
        for line in response.text.splitlines()
        if line.startswith("data: ")
    ]


def test_completed_run_projects_lifecycle_answer_and_bounded_state() -> None:
    client = TestClient(app)
    session_id = _session(client)

    events = _events(client.post("/ag-ui", json=_input(session_id, "agui-turn-1")))

    assert events[0] == {
        "type": "RUN_STARTED",
        "threadId": session_id,
        "runId": "agui-turn-1",
    }
    assert events[-1]["type"] == "RUN_FINISHED"
    assert events[-1]["outcome"] == {"type": "success"}
    assert any(event["type"] == "TEXT_MESSAGE_CONTENT" for event in events)
    state = next(event["snapshot"] for event in events if event["type"] == "STATE_SNAPSHOT")
    assert state["cellxp"]["session_id"] == session_id
    assert state["cellxp"]["run_id"] == events[-1]["result"]["cellxpRunId"]
    assert state["cellxp"]["status"] == "completed"
    assert "report" not in state["cellxp"]


def test_clarification_interrupt_resumes_existing_cellxp_run() -> None:
    client = TestClient(app)
    session_id = _session(client, "Clarification workspace")

    first = _events(
        client.post(
            "/ag-ui",
            json=_input(session_id, "agui-ambiguous-1", message="smoke"),
        )
    )
    finished = first[-1]
    assert finished["type"] == "RUN_FINISHED"
    assert finished["outcome"]["type"] == "interrupt"
    interrupt = finished["outcome"]["interrupts"][0]
    assert interrupt["reason"] == "input_required"
    state = [event["snapshot"] for event in first if event["type"] == "STATE_SNAPSHOT"][-1]
    canonical_run_id = state["cellxp"]["run_id"]

    resumed = _events(
        client.post(
            "/ag-ui",
            json=_input(
                session_id,
                "agui-ambiguous-resume-1",
                state=state,
                resume=[
                    {
                        "interruptId": interrupt["id"],
                        "status": "resolved",
                        "payload": {
                            "selected_option_ids": [],
                            "freeform": "human GRCh38 variant effect",
                        },
                    }
                ],
            ),
        )
    )

    assert resumed[-1]["type"] == "RUN_FINISHED"
    assert resumed[-1]["outcome"] == {"type": "success"}
    assert resumed[-1]["result"]["cellxpRunId"] == canonical_run_id
    assert runtime.get_run(canonical_run_id)["status"] == "completed"


def test_artifacts_are_named_tool_calls_with_refs_not_payloads() -> None:
    run_input = RunAgentInput.model_validate(_input("session-1", "agui-1"))
    artifact = {
        "id": "artifact-1",
        "run_id": "cellxp-run-1",
        "type": "structure_3d",
        "title": "Predicted structure",
        "status": "ready",
        "summary": {"confidence": "high"},
        "actionable": False,
        "review_status": "not_required",
        "created_at": "2026-08-22T00:00:00Z",
        "payload": {"pdb": "must-not-cross-ag-ui"},
        "storage_ref": "s3://private/raw.pdb",
    }
    snapshot = {
        "id": "cellxp-run-1",
        "session_id": "session-1",
        "status": "completed",
        "steps": [],
        "evidence": [],
        "artifacts": [artifact],
        "errors": [],
        "provider": "openai_compatible",
        "model": "Qwen/Qwen3.8-27B",
    }

    events = [
        event.model_dump(mode="json", by_alias=True, exclude_none=True)
        for event in snapshot_events(run_input, snapshot)
    ]
    start = next(event for event in events if event["type"] == "TOOL_CALL_START")
    args = next(event for event in events if event["type"] == "TOOL_CALL_ARGS")

    assert start["toolCallName"] == "render_cellxp_artifact"
    assert json.loads(args["delta"])["artifact"]["id"] == artifact["id"]
    assert "payload" not in args["delta"]
    assert "storage_ref" not in args["delta"]
    assert project_state(snapshot)["cellxp"]["model"]["name"] == "Qwen/Qwen3.8-27B"
