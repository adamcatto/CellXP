"""Validate golden catalogs and score deterministic release-gate result shapes."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence

import httpx


CATALOG_DIR = Path(__file__).parent / "golden_queries"
REQUIRED_FIELDS = frozenset({"id", "capability", "expected", "added_at", "last_reviewed_at"})


def catalog_paths(catalog_dir: Path = CATALOG_DIR) -> list[Path]:
    """Return golden-query catalogs in deterministic order."""

    return sorted(catalog_dir.rglob("*.jsonl"))


def validate_catalog(path: Path) -> list[str]:
    """Return human-readable structural errors for one JSONL catalog."""

    errors: list[str] = []
    for line_number, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not raw_line.strip():
            continue
        try:
            record = json.loads(raw_line)
        except json.JSONDecodeError as exc:
            errors.append(f"{path}:{line_number}: invalid JSON: {exc.msg}")
            continue
        if not isinstance(record, dict):
            errors.append(f"{path}:{line_number}: record must be a JSON object")
            continue
        missing = sorted(REQUIRED_FIELDS - record.keys())
        if missing:
            errors.append(f"{path}:{line_number}: missing fields: {', '.join(missing)}")
    return errors


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    """Load JSON-object records from a JSONL file after structural parsing."""
    records: list[dict[str, Any]] = []
    for line_number, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not raw_line.strip():
            continue
        value = json.loads(raw_line)
        if not isinstance(value, dict):
            raise ValueError(f"{path}:{line_number}: record must be a JSON object")
        records.append(value)
    return records


def score_expected_shape(
    query: dict[str, Any], snapshot: dict[str, Any]
) -> list[dict[str, object]]:
    """Return deterministic checks for expectations that do not require a rubric evaluator."""
    expected = query.get("expected", {})
    checks: list[dict[str, object]] = []

    def check(name: str, passed: bool, detail: str) -> None:
        checks.append({"name": name, "passed": passed, "detail": detail})

    artifact_types = {item.get("type") for item in snapshot.get("artifacts", [])}
    for requirement in expected.get("required_artifacts", []):
        required = requirement.get("type")
        check(f"artifact:{required}", required in artifact_types, f"required artifact {required}")

    evidence_sources = {
        str(item.get("source", "")).lower() for item in snapshot.get("evidence", [])
    }
    for source in expected.get("required_evidence_sources", []):
        normalized = str(source).lower()
        check(
            f"evidence:{source}", normalized in evidence_sources,
            f"required evidence source {source}",
        )

    observed_models = {
        str(snapshot.get("model", "")).lower(),
        *(str(item).lower() for item in snapshot.get("models", [])),
        *(str(step.get("tool", "")).lower() for step in snapshot.get("steps", [])),
    }
    for requirement in expected.get("required_models", []):
        model = str(requirement.get("name", "")).lower()
        matched = any(model and model in observed for observed in observed_models)
        check(f"model:{model}", matched, f"required model {model}")

    if expected.get("must_emit_review_gate"):
        emitted = bool(snapshot.get("pending_review") or snapshot.get("review_emitted"))
        check("review_gate", emitted, "run must emit a review gate")
    if expected.get("must_clarify"):
        emitted = bool(
            snapshot.get("pending_clarification") or snapshot.get("clarification_emitted")
        )
        check("clarification", emitted, "run must request clarification")
    if expected.get("must_refuse"):
        check("refusal", bool(snapshot.get("refused")), "run must refuse")

    expected_order = expected.get("ordered_capabilities", [])
    if expected_order:
        observed_order = [
            item.get("capability") for item in snapshot.get("plan", {}).get("subtasks", [])
        ]
        positions = [observed_order.index(item) for item in expected_order if item in observed_order]
        passed = len(positions) == len(expected_order) and positions == sorted(positions)
        check("capability_order", passed, f"required order: {expected_order}")

    return checks


def evaluate_results(
    results_path: Path, catalog_dir: Path = CATALOG_DIR
) -> dict[str, object]:
    """Join result snapshots to golden queries and compute the deterministic gate report."""
    queries = {
        record["id"]: record
        for path in catalog_paths(catalog_dir)
        for record in load_jsonl(path)
    }
    results = {record["query_id"]: record for record in load_jsonl(results_path)}
    scored: list[dict[str, object]] = []
    for query_id, query in queries.items():
        result = results.get(query_id)
        if result is None:
            checks = [{"name": "result_present", "passed": False, "detail": "missing result"}]
        else:
            checks = score_expected_shape(query, result.get("snapshot", result))
        passed = bool(checks) and all(bool(item["passed"]) for item in checks)
        scored.append({"query_id": query_id, "passed": passed, "checks": checks})
    passed_count = sum(bool(item["passed"]) for item in scored)
    return {
        "schema_version": "1.0", "query_count": len(scored), "passed": passed_count,
        "failed": len(scored) - passed_count,
        "pass_rate": passed_count / len(scored) if scored else 0.0,
        "results": scored,
    }


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def dispatch_api_runs(
    api_base_url: str,
    archive_dir: Path,
    *,
    catalog_dir: Path = CATALOG_DIR,
    timeout_seconds: float = 900.0,
    poll_seconds: float = 1.0,
    token: str | None = None,
    client: httpx.Client | None = None,
) -> dict[str, object]:
    """Dispatch public golden queries to a real API and create a non-overwritable archive."""
    if archive_dir.exists():
        raise FileExistsError(f"archive already exists: {archive_dir}")
    archive_dir.mkdir(parents=True)
    paths = catalog_paths(catalog_dir)
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    owns_client = client is None
    http = client or httpx.Client(
        base_url=api_base_url.rstrip("/") + "/", headers=headers, timeout=30.0
    )
    archive_id = archive_dir.name
    records: list[dict[str, object]] = []
    terminal = {"completed", "failed", "cancelled", "awaiting_input", "awaiting_review"}
    try:
        for path in paths:
            for query in load_jsonl(path):
                query_id = str(query["id"])
                started_at = datetime.now(timezone.utc).isoformat()
                record: dict[str, object] = {
                    "query_id": query_id, "catalog": str(path.relative_to(catalog_dir)),
                    "dispatched_at": started_at,
                }
                try:
                    defaults = {
                        key: query[key] for key in ("organism", "assembly") if query.get(key)
                    }
                    session_response = http.post(
                        "sessions",
                        json={
                            "type": "genome_editing"
                            if query.get("capability") in {"crispr", "crispr_design", "inverse_design"}
                            else "general",
                            "title": f"Evaluation {query_id}", "defaults": defaults,
                        },
                    )
                    session_response.raise_for_status()
                    session_id = str(session_response.json()["id"])
                    run_response = http.post(
                        f"sessions/{session_id}/runs",
                        json={
                            "message": query.get("message"),
                            "client_request_id": f"eval:{archive_id}:{query_id}",
                            "overrides": defaults,
                        },
                    )
                    run_response.raise_for_status()
                    run_id = str(run_response.json()["run_id"])
                    deadline = time.monotonic() + timeout_seconds
                    while True:
                        snapshot_response = http.get(f"runs/{run_id}")
                        snapshot_response.raise_for_status()
                        snapshot = snapshot_response.json()
                        if snapshot.get("status") in terminal:
                            break
                        if time.monotonic() >= deadline:
                            raise TimeoutError(f"run {run_id} exceeded {timeout_seconds}s")
                        time.sleep(poll_seconds)
                    record.update(
                        {
                            "session_id": session_id, "run_id": run_id,
                            "completed_at": datetime.now(timezone.utc).isoformat(),
                            "snapshot": snapshot,
                        }
                    )
                except (httpx.HTTPError, KeyError, TypeError, ValueError, TimeoutError) as exc:
                    record["dispatch_error"] = {
                        "type": type(exc).__name__, "message": str(exc),
                    }
                records.append(record)
    finally:
        if owns_client:
            http.close()

    results_path = archive_dir / "results.jsonl"
    results_path.write_text(
        "".join(json.dumps(record, sort_keys=True) + "\n" for record in records),
        encoding="utf-8",
    )
    manifest: dict[str, object] = {
        "schema_version": "1.0", "archive_id": archive_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "build_revision": os.getenv("CELLXP_BUILD_REVISION", "unknown"),
        "api_base_url": api_base_url.rstrip("/"),
        "catalogs": [
            {"path": str(path.relative_to(catalog_dir)), "sha256": _sha256(path)}
            for path in paths
        ],
        "results": {"path": "results.jsonl", "sha256": _sha256(results_path)},
        "query_count": len(records),
        "dispatch_errors": sum("dispatch_error" in record for record in records),
        "immutable": True,
    }
    manifest_path = archive_dir / "manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    results_path.chmod(0o444)
    manifest_path.chmod(0o444)
    return manifest


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Inspect and validate CellXP golden-query catalogs.",
    )
    subparsers = parser.add_subparsers(dest="command")
    subparsers.add_parser("list", help="list discovered JSONL catalogs")
    subparsers.add_parser("validate", help="validate JSONL syntax and required record fields")
    evaluate = subparsers.add_parser(
        "evaluate", help="score deterministic expected shapes against recorded run snapshots"
    )
    evaluate.add_argument("results", type=Path, help="JSONL with query_id and snapshot fields")
    evaluate.add_argument("--catalog-dir", type=Path, default=CATALOG_DIR)
    evaluate.add_argument("--output", type=Path)
    dispatch = subparsers.add_parser(
        "dispatch", help="run golden queries through a deployed API and archive snapshots"
    )
    dispatch.add_argument("--api-base-url", required=True)
    dispatch.add_argument("--archive-dir", type=Path, required=True)
    dispatch.add_argument("--catalog-dir", type=Path, default=CATALOG_DIR)
    dispatch.add_argument("--timeout-seconds", type=float, default=900.0)
    dispatch.add_argument("--poll-seconds", type=float, default=1.0)
    dispatch.add_argument("--token", default=os.getenv("CELLXP_API_TOKEN"))
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command is None:
        parser.print_help()
        return 0

    paths = catalog_paths()
    if args.command == "list":
        for path in paths:
            print(path.relative_to(Path(__file__).parent))
        return 0

    errors = [error for path in paths for error in validate_catalog(path)]
    if errors:
        for error in errors:
            print(error)
        return 1
    if args.command == "validate":
        print(f"Validated {len(paths)} golden-query catalog(s).")
        return 0

    if args.command == "dispatch":
        try:
            manifest = dispatch_api_runs(
                args.api_base_url, args.archive_dir, catalog_dir=args.catalog_dir,
                timeout_seconds=args.timeout_seconds, poll_seconds=args.poll_seconds,
                token=args.token,
            )
        except FileExistsError as exc:
            print(exc)
            return 1
        print(json.dumps(manifest, indent=2, sort_keys=True))
        return 0 if manifest["dispatch_errors"] == 0 else 1

    report = evaluate_results(args.results, args.catalog_dir)
    rendered = json.dumps(report, indent=2, sort_keys=True)
    if args.output:
        args.output.write_text(rendered + "\n", encoding="utf-8")
    else:
        print(rendered)
    return 0 if report["failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
