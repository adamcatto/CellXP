"""T4 contract path: session -> run -> ordered SSE -> durable snapshot."""

import json

import pytest
from cellxp.api.main import app
from cellxp.api.runtime import runtime
from fastapi.testclient import TestClient


@pytest.fixture(autouse=True)
def clean_runtime():
    runtime.reset()
    yield
    runtime.reset()


def _session(client: TestClient) -> str:
    response = client.post(
        "/api/v1/sessions",
        json={
            "type": "variant_interpretation",
            "title": "Variant workspace",
            "defaults": {"organism": "human", "assembly": "GRCh38"},
        },
    )
    assert response.status_code == 201
    return response.json()["id"]


def _sse_frames(body: str) -> list[dict[str, object]]:
    frames = []
    for block in body.strip().split("\n\n"):
        fields = dict(line.split(": ", 1) for line in block.splitlines())
        frames.append(
            {
                "id": int(fields["id"]),
                "event": fields["event"],
                "data": json.loads(fields["data"]),
            }
        )
    return frames


def test_variant_run_is_idempotent_and_stream_is_replayable() -> None:
    client = TestClient(app)
    session_id = _session(client)
    payload = {"message": "What does rs699 do?", "client_request_id": "browser-turn-1"}

    created = client.post(f"/api/v1/sessions/{session_id}/runs", json=payload)
    duplicate = client.post(f"/api/v1/sessions/{session_id}/runs", json=payload)

    assert created.status_code == 202
    assert duplicate.json()["run_id"] == created.json()["run_id"]
    run_id = created.json()["run_id"]
    snapshot = client.get(f"/api/v1/runs/{run_id}").json()
    assert snapshot["status"] == "completed"
    assert snapshot["report"]
    assert snapshot["provider"] == "ollama"

    stream = client.get(f"/api/v1/runs/{run_id}/events")
    assert stream.headers["content-type"].startswith("text/event-stream")
    frames = _sse_frames(stream.text)
    assert [frame["id"] for frame in frames] == list(range(1, len(frames) + 1))
    assert frames[-1]["event"] == "run.completed"

    replay = client.get(
        f"/api/v1/runs/{run_id}/events", headers={"Last-Event-ID": str(frames[-2]["id"])}
    )
    replay_frames = _sse_frames(replay.text)
    assert [frame["id"] for frame in replay_frames] == [frames[-1]["id"]]


def test_ambiguous_run_can_resume_from_clarification() -> None:
    client = TestClient(app)
    response = client.post(
        "/api/v1/sessions",
        json={"type": "general", "title": "General workspace"},
    )
    session_id = response.json()["id"]
    created = client.post(
        f"/api/v1/sessions/{session_id}/runs",
        json={"message": "smoke", "client_request_id": "ambiguous-1"},
    )
    run_id = created.json()["run_id"]
    snapshot = client.get(f"/api/v1/runs/{run_id}").json()

    assert snapshot["status"] == "awaiting_input"
    clarification = snapshot["pending_clarification"]
    answer = client.post(
        f"/api/v1/runs/{run_id}/clarifications/{clarification['id']}/answer",
        json={"selected_option_ids": [], "freeform": "human GRCh38 variant effect"},
    )
    assert answer.status_code == 204
    assert client.get(f"/api/v1/runs/{run_id}").json()["status"] == "completed"
