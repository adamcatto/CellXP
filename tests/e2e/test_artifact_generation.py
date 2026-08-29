"""T4 lifecycle checks for workspace revisions, reproduction, and cancellation."""

from cellxp.api.main import app
from cellxp.api.runtime import runtime
from fastapi.testclient import TestClient


def test_session_revision_guard_and_run_reproduction() -> None:
    runtime.reset()
    client = TestClient(app)
    created = client.post(
        "/api/v1/sessions",
        json={
            "type": "variant_interpretation",
            "title": "Original",
            "defaults": {"organism": "human", "assembly": "GRCh38"},
        },
    ).json()

    stale = client.patch(
        f"/api/v1/sessions/{created['id']}",
        json={"title": "Stale", "expected_revision": 1},
    )
    assert stale.status_code == 409
    updated = client.patch(
        f"/api/v1/sessions/{created['id']}",
        json={"title": "Updated", "expected_revision": 0},
    )
    assert updated.status_code == 200
    assert updated.json()["revision"] == 1

    run = client.post(
        f"/api/v1/sessions/{created['id']}/runs",
        json={"message": "Interpret rs699", "client_request_id": "original-run"},
    ).json()
    reproduced = client.post(f"/api/v1/runs/{run['run_id']}/reproduce")
    assert reproduced.status_code == 200
    reproduced_snapshot = client.get(
        f"/api/v1/runs/{reproduced.json()['run_id']}"
    ).json()
    assert reproduced_snapshot["reproduces_run_id"] == run["run_id"]

    # Cancellation is idempotent and cannot rewrite an already-terminal run.
    assert client.post(f"/api/v1/runs/{run['run_id']}/cancel").status_code == 204
    assert client.post(f"/api/v1/runs/{run['run_id']}/cancel").status_code == 204
    assert client.get(f"/api/v1/runs/{run['run_id']}").json()["status"] == "completed"
