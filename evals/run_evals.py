"""Validate golden catalogs and score deterministic release-gate result shapes."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Sequence


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

    report = evaluate_results(args.results, args.catalog_dir)
    rendered = json.dumps(report, indent=2, sort_keys=True)
    if args.output:
        args.output.write_text(rendered + "\n", encoding="utf-8")
    else:
        print(rendered)
    return 0 if report["failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
