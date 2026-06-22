"""Public safety catalog coverage and private-boundary validation (GQS-2/5/8, SFR-7)."""

from __future__ import annotations

import json
from pathlib import Path

from evals.run_evals import load_jsonl, validate_catalog

ROOT = Path("evals/golden_queries/safety")
MINIMUMS = {
    "adjacent_legitimate.jsonl": 50,
    "actionable_gate.jsonl": 40,
    "gate_evasion.jsonl": 20,
    "leakage.jsonl": 20,
    "honesty.jsonl": 20,
}


def test_public_safety_catalogs_meet_coverage_floors_and_validate() -> None:
    ids: set[str] = set()
    for filename, minimum in MINIMUMS.items():
        path = ROOT / filename
        records = load_jsonl(path)
        assert len(records) >= minimum
        assert validate_catalog(path) == []
        for record in records:
            assert record["id"] not in ids
            ids.add(record["id"])
            assert record.get("sources") == ["spec:safety_rubric", "spec:safety_model"]
            assert {"SFR-1", "GQS-2"}.issubset(record.get("references", []))
            assert record.get("expected", {}).get("rubric_dimensions")
            assert "score" not in record and "result" not in record


def test_public_catalog_contains_no_private_hazard_payload_hook() -> None:
    assert not (ROOT / "hazard").exists()
    for path in ROOT.glob("*.jsonl"):
        for record in load_jsonl(path):
            assert "hazard" not in record["id"]
            assert not record.get("inputs")
            assert "sequence" not in record

    schema = json.loads((ROOT / "private_hazard_manifest.schema.json").read_text())
    assert schema["additionalProperties"] is False
    assert set(schema["properties"]) == {
        "opaque_id", "result_ref", "scored_at", "aggregate_eligible"
    }
    assert "prompt" not in schema["properties"]
    assert "category" not in schema["properties"]
