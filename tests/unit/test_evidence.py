"""Evidence/confidence/provenance contract tests (Wave 0)."""

import pytest

from cellxp.domain.enums import ConfidenceBand, SourceKind
from cellxp.domain.evidence import Confidence, EvidenceItem, Provenance
from cellxp.domain.models import EvidenceItem as ReexportedEvidenceItem


def test_confidence_requires_band():
    c = Confidence(band=ConfidenceBand.HIGH)
    assert c.score is None and c.basis is None


def test_confidence_score_must_be_unit_interval():
    Confidence(band=ConfidenceBand.MEDIUM, score=0.0)
    Confidence(band=ConfidenceBand.MEDIUM, score=1.0)
    with pytest.raises(ValueError):
        Confidence(band=ConfidenceBand.MEDIUM, score=1.5)
    with pytest.raises(ValueError):
        Confidence(band=ConfidenceBand.MEDIUM, score=-0.1)


def test_provenance_defaults_are_empty_not_shared():
    p1 = Provenance()
    p2 = Provenance()
    p1.params["a"] = 1
    assert p2.params == {}  # default_factory, not a shared mutable default
    assert p1.nondeterministic is False and p1.cache_hit is False


def test_evidence_item_autogenerates_unique_ids():
    e1 = EvidenceItem(source="AlphaGenome", source_kind=SourceKind.MODEL, claim="x",
                      confidence=Confidence(band=ConfidenceBand.LOW))
    e2 = EvidenceItem(source="AlphaGenome", source_kind=SourceKind.MODEL, claim="x",
                      confidence=Confidence(band=ConfidenceBand.LOW))
    assert e1.id and e2.id and e1.id != e2.id


def test_evidence_item_roundtrips_json():
    e = EvidenceItem(
        source="ClinVar",
        source_kind=SourceKind.DATABASE,
        claim="pathogenic",
        value={"rows": 3},
        confidence=Confidence(band=ConfidenceBand.HIGH, score=0.9, basis="curated record"),
        provenance=Provenance(tool="clinvar", tool_version="2026-01", citations=["VCV000123"]),
    )
    assert EvidenceItem.model_validate_json(e.model_dump_json()) == e


def test_models_reexports_canonical_evidence_item():
    assert ReexportedEvidenceItem is EvidenceItem
