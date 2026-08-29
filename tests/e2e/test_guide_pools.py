from cellxp.api.main import app
from cellxp.api.runtime import runtime
from fastapi.testclient import TestClient


def test_api_persists_and_revises_ordered_guide_pool():
    runtime.reset()
    client = TestClient(app)
    session = client.post("/api/v1/sessions", json={
        "type": "genome_editing", "title": "Pool", "defaults": {"review_posture": "strict"},
    }).json()
    artifact_id = "018f0000-0000-7000-8000-000000000032"
    created = client.post(f"/api/v1/artifacts/{artifact_id}/guide-pools", json={
        "session_id": session["id"], "name": "Primary", "guide_ids": ["guide-2", "guide-1"],
    })
    assert created.status_code == 201
    pool = created.json()
    assert pool["guide_ids"] == ["guide-2", "guide-1"]

    revised = client.put(
        f"/api/v1/artifacts/{artifact_id}/guide-pools/{pool['id']}",
        json={"session_id": session["id"], "name": "Primary", "guide_ids": ["guide-1"],
              "expected_revision": 0},
    )
    assert revised.status_code == 200
    assert revised.json()["revision"] == 1
    stale = client.put(
        f"/api/v1/artifacts/{artifact_id}/guide-pools/{pool['id']}",
        json={"session_id": session["id"], "name": "Primary", "guide_ids": ["guide-2"],
              "expected_revision": 0},
    )
    assert stale.status_code == 409
    listed = client.get(f"/api/v1/artifacts/{artifact_id}/guide-pools").json()["items"]
    assert listed[0]["guide_ids"] == ["guide-1"]
