"""Artifact content/export and persisted review-audit API contract coverage."""

from __future__ import annotations

from fastapi.testclient import TestClient

from cellxp.api.main import app
from cellxp.api.runtime import DurableRuntime
from cellxp.api.schemas import CreateRunRequest, CreateSessionRequest
from cellxp.domain.clock import utc_now_iso

RUN_ID = "00000000-0000-4000-8000-000000000001"
PENDING_ID = "00000000-0000-4000-8000-000000000002"
APPROVED_ID = "00000000-0000-4000-8000-000000000003"


def _runtime(tmp_path) -> tuple[DurableRuntime, str]:
    runtime = DurableRuntime(f"sqlite:///{tmp_path / 'runtime.db'}")
    session = runtime.create_session(CreateSessionRequest(type="genome_editing", title="Review"))
    run_id = RUN_ID
    request = CreateRunRequest(message="review", client_request_id="review-1")
    now = utc_now_iso()
    snapshot = {
        "id": run_id, "session_id": session.id, "status": "completed", "message": "review",
        "steps": [], "evidence": [], "errors": [], "created_at": now, "updated_at": now,
        "artifacts": [
            {
                "id": PENDING_ID, "type": "guide_table", "title": "Pending guides",
                "status": "ready", "summary": {"guides": ["candidate-1"]},
                "actionable": True, "review_status": "pending", "created_at": now,
            },
            {
                "id": APPROVED_ID, "type": "guide_table", "title": "Approved guides",
                "status": "ready", "summary": {"guides": ["candidate-2"]},
                "actionable": True, "review_status": "approved", "created_at": now,
            },
        ],
    }
    runtime.repository.save_run(snapshot, request)
    record = runtime.refresh_run(run_id)
    runtime._on_review_requested(record, {
        "id": "review-artifact-approved", "artifact_ref": {"id": APPROVED_ID}
    })
    runtime._audit_review_decision(
        record, APPROVED_ID, "review-artifact-approved", True
    )
    return runtime, run_id


def test_artifact_manifest_content_export_and_audit_are_persisted(
    tmp_path, monkeypatch
) -> None:
    runtime, run_id = _runtime(tmp_path)
    from cellxp.api.routers import artifacts, runs

    monkeypatch.setattr(artifacts, "runtime", runtime)
    monkeypatch.setattr(runs, "runtime", runtime)
    monkeypatch.setenv("OBJECT_STORE_URL", f"file://{tmp_path / 'objects'}")
    client = TestClient(app)

    manifest = client.get(f"/api/v1/artifacts/{APPROVED_ID}")
    assert manifest.status_code == 200
    assert manifest.json()["run_id"] == run_id
    assert manifest.json()["storage_ref"] is None

    content = client.get(f"/api/v1/artifacts/{APPROVED_ID}/content")
    assert content.status_code == 200
    assert content.headers["etag"]
    assert content.json() == {"guides": ["candidate-2"]}

    blocked = client.post(
        f"/api/v1/artifacts/{PENDING_ID}/exports", json={"format": "json"}
    )
    assert blocked.status_code == 409

    exported = client.post(
        f"/api/v1/artifacts/{APPROVED_ID}/exports", json={"format": "json"}
    )
    assert exported.status_code == 201
    assert exported.json()["content_hash"]
    stored = DurableRuntime(f"sqlite:///{tmp_path / 'runtime.db'}")
    _, approved = stored.find_artifact(APPROVED_ID)
    assert approved["exports"][0]["id"] == exported.json()["id"]

    audit = client.get(f"/api/v1/runs/{run_id}/audit")
    assert audit.status_code == 200
    assert audit.json()["chain_valid"] is True
    assert {item["event_type"] for item in audit.json()["items"]} == {
        "review.requested", "review.decided", "actionable.emitted", "side_effect.performed",
    }
    assert all(item["subject_ref"] == APPROVED_ID for item in audit.json()["items"])
