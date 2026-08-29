"""Opt-in M1-M3 deployed review/audit/deep-link acceptance evidence collector."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import time
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _now() -> str:
    return datetime.now(UTC).isoformat()


def collect_deployed_acceptance(
    api_base_url: str,
    archive_dir: Path,
    *,
    crispr_message: str = "Design reviewed CRISPR candidates for a standard control-gene benchmark.",
    evidence_message: str = "Summarize cited GWAS evidence for the public rs2476601 benchmark.",
    timeout_seconds: float = 900.0,
    poll_seconds: float = 1.0,
    token: str | None = None,
    client: httpx.Client | None = None,
) -> dict[str, Any]:
    """Exercise deployed acceptance routes and archive observations without inventing evidence."""
    if archive_dir.exists():
        raise FileExistsError(f"archive already exists: {archive_dir}")
    archive_dir.mkdir(parents=True)
    owns_client = client is None
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    http = client or httpx.Client(
        base_url=api_base_url.rstrip("/") + "/", headers=headers, timeout=30.0
    )
    observations: list[dict[str, Any]] = []
    checks: dict[str, bool] = {}
    run_statuses: dict[str, str] = {}

    def request(method: str, path: str, **kwargs: Any) -> httpx.Response:
        response = http.request(method, path, **kwargs)
        try:
            body: object = response.json()
        except (json.JSONDecodeError, ValueError):
            body = response.text[:2000]
        observations.append(
            {"method": method, "path": path, "status_code": response.status_code, "body": body}
        )
        return response

    def create_run(message: str, request_id: str, session_type: str = "general") -> str:
        session = request(
            "POST", "sessions",
            json={
                "type": session_type, "title": f"Acceptance {request_id}",
                "defaults": {"review_posture": "strict"} if session_type == "genome_editing" else {},
            },
        )
        session.raise_for_status()
        session_id = str(session.json()["id"])
        run = request(
            "POST", f"sessions/{session_id}/runs",
            json={"message": message, "client_request_id": request_id},
        )
        run.raise_for_status()
        return str(run.json()["run_id"])

    def wait_for(run_id: str, statuses: set[str]) -> dict[str, Any]:
        deadline = time.monotonic() + timeout_seconds
        while True:
            response = request("GET", f"runs/{run_id}")
            response.raise_for_status()
            snapshot = response.json()
            status = str(snapshot.get("status"))
            run_statuses[run_id] = status
            if status in statuses:
                return snapshot
            if time.monotonic() >= deadline:
                raise TimeoutError(f"run {run_id} did not reach {sorted(statuses)}")
            time.sleep(poll_seconds)

    try:
        review_run = create_run(crispr_message, f"acceptance-review:{archive_dir.name}", "genome_editing")
        paused = wait_for(review_run, {"awaiting_review", "failed", "cancelled", "completed"})
        pending = paused.get("pending_review") if paused.get("status") == "awaiting_review" else None
        checks["review_requested"] = isinstance(pending, dict)
        if not isinstance(pending, dict):
            raise RuntimeError("deployed CRISPR run did not emit a review request")  # noqa: TRY004
        review_id = str(pending["id"])
        artifact = pending.get("artifact_ref", {})
        artifact_id = str(artifact.get("id", "")) if isinstance(artifact, dict) else ""
        checks["actionable_subject_linked"] = bool(artifact_id)

        pre_export = request("POST", f"artifacts/{artifact_id}/exports", json={"format": "json"})
        checks["preapproval_export_restricted"] = pre_export.status_code in {403, 409, 423}

        approval = request(
            "POST", f"runs/{review_run}/reviews/{review_id}/decision",
            json={
                "decision": "approve", "note": "deployed acceptance verification",
                "expected_run_status": "awaiting_review",
            },
        )
        checks["approval_accepted"] = approval.status_code in {200, 202, 204}
        approval.raise_for_status()
        completed = wait_for(review_run, {"completed", "failed", "cancelled"})
        checks["run_completed_after_approval"] = completed.get("status") == "completed"

        audit = request("GET", f"runs/{review_run}/audit")
        checks["audit_endpoint_available"] = audit.status_code == 200
        audit_items = audit.json().get("items", []) if audit.status_code == 200 else []
        event_types = {item.get("event_type") for item in audit_items if isinstance(item, dict)}
        checks["audit_review_requested"] = "review.requested" in event_types
        checks["audit_review_decided"] = "review.decided" in event_types
        checks["audit_actionable_emitted"] = "actionable.emitted" in event_types
        checks["audit_chain_valid"] = bool(audit.status_code == 200 and audit.json().get("chain_valid"))
        checks["audit_subject_linked"] = any(
            item.get("subject_ref") == artifact_id and item.get("run_id") == review_run
            for item in audit_items if isinstance(item, dict)
        )

        post_export = request("POST", f"artifacts/{artifact_id}/exports", json={"format": "json"})
        checks["approved_export_available"] = post_export.status_code in {200, 201, 202}

        evidence_run = create_run(evidence_message, f"acceptance-deeplink:{archive_dir.name}")
        wait_for(evidence_run, {"completed", "failed", "cancelled"})
        evidence_response = request("GET", f"runs/{evidence_run}/evidence")
        steps_response = request("GET", f"runs/{evidence_run}/steps")
        checks["evidence_endpoint_available"] = evidence_response.status_code == 200
        checks["steps_endpoint_available"] = steps_response.status_code == 200
        evidence = evidence_response.json().get("items", []) if evidence_response.status_code == 200 else []
        steps = steps_response.json().get("items", []) if steps_response.status_code == 200 else []
        step_ids = {item.get("id") for item in steps if isinstance(item, dict)}
        linked = [item for item in evidence if isinstance(item, dict) and item.get("step_id") in step_ids]
        checks["evidence_step_deep_link"] = bool(linked)
        checks["citation_deep_link"] = any(
            item.get("kind") == "citation" and item.get("source") for item in linked
        )
    except (httpx.HTTPError, KeyError, TypeError, ValueError, TimeoutError, RuntimeError) as exc:
        observations.append({"collector_error": {"type": type(exc).__name__, "message": str(exc)}})
    finally:
        if owns_client:
            http.close()

    review_keys = {
        "review_requested", "actionable_subject_linked", "preapproval_export_restricted",
        "approval_accepted", "run_completed_after_approval", "audit_endpoint_available",
        "audit_review_requested", "audit_review_decided", "audit_actionable_emitted",
        "audit_chain_valid", "audit_subject_linked", "approved_export_available",
    }
    deep_link_keys = {
        "evidence_endpoint_available", "steps_endpoint_available",
        "evidence_step_deep_link", "citation_deep_link",
    }
    acceptance = {
        "review_approve_audit": all(checks.get(key) is True for key in review_keys),
        "run_inspector_deep_link": all(checks.get(key) is True for key in deep_link_keys),
    }
    evidence_manifest = {
        "schema_version": "1.0", "acceptance": acceptance,
        "telemetry": {
            "acceptance_runs": {
                "count": len(run_statuses), "statuses": run_statuses,
                "collected_at": _now(),
            }
        },
        "notes": [
            "Acceptance values derive only from deployed API observations.",
            "This small acceptance sample is not used as release run-success or latency evidence.",
        ],
    }
    observations_path = archive_dir / "observations.json"
    evidence_path = archive_dir / "evidence.json"
    observations_path.write_text(json.dumps({"checks": checks, "requests": observations}, indent=2, sort_keys=True) + "\n")
    evidence_path.write_text(json.dumps(evidence_manifest, indent=2, sort_keys=True) + "\n")
    manifest = {
        "schema_version": "1.0", "created_at": _now(),
        "build_revision": os.getenv("CELLXP_BUILD_REVISION", "unknown"),
        "api_base_url": api_base_url.rstrip("/"), "immutable": True,
        "files": {
            "observations.json": _sha256(observations_path),
            "evidence.json": _sha256(evidence_path),
        },
    }
    manifest_path = archive_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    for path in (observations_path, evidence_path, manifest_path):
        path.chmod(0o444)
    return {"manifest": manifest, "evidence": evidence_manifest, "checks": checks}


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--api-base-url", required=True)
    parser.add_argument("--archive-dir", type=Path, required=True)
    parser.add_argument("--crispr-message", default=None)
    parser.add_argument("--evidence-message", default=None)
    parser.add_argument("--timeout-seconds", type=float, default=900.0)
    parser.add_argument("--poll-seconds", type=float, default=1.0)
    parser.add_argument("--token", default=os.getenv("CELLXP_API_TOKEN"))
    args = parser.parse_args(argv)
    kwargs = {
        key: value for key, value in {
            "crispr_message": args.crispr_message, "evidence_message": args.evidence_message,
        }.items() if value is not None
    }
    try:
        result = collect_deployed_acceptance(
            args.api_base_url, args.archive_dir, timeout_seconds=args.timeout_seconds,
            poll_seconds=args.poll_seconds, token=args.token, **kwargs,
        )
    except FileExistsError as exc:
        print(exc)
        return 1
    print(json.dumps(result["evidence"], indent=2, sort_keys=True))
    return 0 if all(result["evidence"]["acceptance"].values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
