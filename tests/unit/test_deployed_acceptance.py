"""Contract tests for opt-in deployed M1-M3 acceptance evidence collection."""

from __future__ import annotations

import json

import httpx

from evals.deployed_acceptance import collect_deployed_acceptance


def passing_handler() -> httpx.MockTransport:
    state = {"runs": 0, "approved": False}

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if request.method == "POST" and path == "/api/v1/sessions":
            return httpx.Response(201, json={"id": f"session-{state['runs'] + 1}"})
        if request.method == "POST" and path.endswith("/runs"):
            state["runs"] += 1
            return httpx.Response(202, json={"run_id": f"run-{state['runs']}"})
        if request.method == "GET" and path == "/api/v1/runs/run-1":
            if not state["approved"]:
                return httpx.Response(200, json={
                    "id": "run-1", "status": "awaiting_review",
                    "pending_review": {
                        "id": "review-1", "artifact_ref": {"id": "artifact-1", "actionable": True},
                    },
                })
            return httpx.Response(200, json={"id": "run-1", "status": "completed"})
        if request.method == "POST" and path.endswith("/reviews/review-1/decision"):
            state["approved"] = True
            return httpx.Response(204)
        if request.method == "POST" and path == "/api/v1/artifacts/artifact-1/exports":
            return httpx.Response(201 if state["approved"] else 409, json={"id": "export-1"})
        if request.method == "GET" and path == "/api/v1/runs/run-1/audit":
            return httpx.Response(200, json={
                "chain_valid": True,
                "items": [
                    {"event_type": event, "run_id": "run-1", "subject_ref": "artifact-1"}
                    for event in ("review.requested", "review.decided", "actionable.emitted")
                ],
            })
        if request.method == "GET" and path == "/api/v1/runs/run-2":
            return httpx.Response(200, json={"id": "run-2", "status": "completed"})
        if request.method == "GET" and path == "/api/v1/runs/run-2/evidence":
            return httpx.Response(200, json={
                "items": [{"id": "ev-1", "kind": "citation", "source": "pubmed", "step_id": "step-1"}]
            })
        if request.method == "GET" and path == "/api/v1/runs/run-2/steps":
            return httpx.Response(200, json={"items": [{"id": "step-1"}]})
        return httpx.Response(404)

    return httpx.MockTransport(handler)


def test_collector_verifies_review_audit_exports_and_deep_links(tmp_path) -> None:
    client = httpx.Client(base_url="https://cellxp.test/api/v1/", transport=passing_handler())
    archive = tmp_path / "acceptance-001"
    result = collect_deployed_acceptance(
        "https://cellxp.test/api/v1", archive, client=client, poll_seconds=0
    )

    assert result["evidence"]["acceptance"] == {
        "review_approve_audit": True, "run_inspector_deep_link": True,
    }
    manifest = json.loads((archive / "manifest.json").read_text())
    assert manifest["files"]["observations.json"]
    assert manifest["files"]["evidence.json"]
    assert json.loads((archive / "evidence.json").read_text())["telemetry"][
        "acceptance_runs"
    ]["count"] == 2


def test_missing_deployed_endpoints_fail_closed_and_are_archived(tmp_path) -> None:
    client = httpx.Client(
        base_url="https://cellxp.test/api/v1/",
        transport=httpx.MockTransport(lambda request: httpx.Response(404)),
    )
    archive = tmp_path / "acceptance-missing"
    result = collect_deployed_acceptance(
        "https://cellxp.test/api/v1", archive, client=client, poll_seconds=0
    )
    assert result["evidence"]["acceptance"] == {
        "review_approve_audit": False, "run_inspector_deep_link": False,
    }
    observations = json.loads((archive / "observations.json").read_text())
    assert observations["requests"][-1]["collector_error"]["type"] == "HTTPStatusError"


def test_acceptance_archive_cannot_be_overwritten(tmp_path) -> None:
    archive = tmp_path / "existing"
    archive.mkdir()
    client = httpx.Client(base_url="https://cellxp.test/api/v1/", transport=passing_handler())
    try:
        collect_deployed_acceptance("https://cellxp.test/api/v1", archive, client=client)
    except FileExistsError:
        pass
    else:
        raise AssertionError("acceptance archive must not be overwritten")
