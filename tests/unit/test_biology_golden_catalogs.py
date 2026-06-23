"""Release-facing validation for public biology golden catalogs."""

from __future__ import annotations

import json
import re
from collections import Counter
from datetime import datetime
from pathlib import Path

CATALOG_DIR = Path("evals/golden_queries")
RELEASE_CATALOGS = {
    "variant_effect.jsonl", "gwas_lookup.jsonl", "structure_prediction.jsonl",
    "crispr_design.jsonl", "inverse_design.jsonl", "composed_evidence.jsonl",
    "binding_prediction.jsonl", "rag_literature.jsonl", "visualization.jsonl",
    "reference_genome.jsonl",
}
EDGE_TAGS = {
    "edge_case", "circular", "circular_bacterial", "missing_assembly", "missing_inputs",
    "missing_edit_spec", "missing_index", "conflicting_evidence", "conflicting_objectives",
    "unsupported", "nonhuman_unsupported", "low_confidence", "intrinsically_disordered",
    "model_limit", "clinical_boundary", "population_limit", "empty_evidence", "no_pam",
    "ref_allele_mismatch", "repetitive_risk", "off_target_floor",
    "underspecified_objective", "partial_target",
}
NON_MODEL_EUKARYOTES = {
    "Saccharomyces cerevisiae", "Gallus gallus", "Aequorea victoria", "Physeter catodon",
    "Arabidopsis thaliana", "Drosophila melanogaster", "Danio rerio",
}


def _records() -> list[dict[str, object]]:
    records: list[dict[str, object]] = []
    for path in sorted(CATALOG_DIR.glob("*.jsonl")):
        if path.name not in RELEASE_CATALOGS:
            continue
        for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            record = json.loads(line)
            record["_catalog"] = path.name
            record["_line"] = line_number
            records.append(record)
    return records


def test_release_biology_catalogs_are_sourced_and_explicit() -> None:
    records = _records()
    ids = [str(record["id"]) for record in records]
    assert len(ids) == len(set(ids))
    for record in records:
        label = f"{record['_catalog']}:{record['_line']}"
        assert re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)+", str(record["id"])), label
        sources = record.get("sources")
        assert isinstance(sources, list) and sources, f"{label}: sources required"
        assert all(str(source).startswith(("doi:", "https://", "spec:")) for source in sources), label
        expected = record.get("expected")
        assert isinstance(expected, dict), label
        assert expected.get("rubric_dimensions"), f"{label}: rubric dimensions required"
        assert any(expected.get(key) for key in (
            "must_contain", "must_clarify", "must_refuse", "required_artifacts",
            "ordered_capabilities",
        )), f"{label}: explicit expected constraint required"
        for field in ("added_at", "last_reviewed_at"):
            datetime.fromisoformat(str(record[field]).replace("Z", "+00:00"))


def test_release_capability_and_composition_floors() -> None:
    records = _records()
    counts = Counter(str(record["capability"]) for record in records)
    for capability in (
        "variant_effect", "gwas", "structure", "crispr", "inverse_design", "binding",
        "rag", "visualization", "reference",
    ):
        assert counts[capability] >= 15, (capability, counts[capability])
    assert counts["composed_evidence"] >= 25
    public_total = sum(
        1 for path in CATALOG_DIR.glob("*.jsonl")
        for line in path.read_text(encoding="utf-8").splitlines() if line.strip()
    )
    assert public_total >= 200


def test_release_organism_and_edge_case_floors() -> None:
    records = _records()
    buckets = {
        "human": sum(record.get("organism") == "Homo sapiens" for record in records),
        "mouse": sum(record.get("organism") == "Mus musculus" for record in records),
        "model_microbe": sum(record.get("organism") == "Escherichia coli" for record in records),
        "exemplar_prokaryote": sum(
            record.get("organism") == "Gluconobacter oxydans" for record in records
        ),
        "plasmid": sum("plasmid" in record.get("tags", []) for record in records),
        "non_model_eukaryote": sum(
            record.get("organism") in NON_MODEL_EUKARYOTES for record in records
        ),
    }
    assert all(count >= 10 for count in buckets.values()), buckets
    edge_cases = sum(bool(EDGE_TAGS.intersection(record.get("tags", []))) for record in records)
    assert edge_cases >= 30, edge_cases
