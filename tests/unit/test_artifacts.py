"""Artifact reference contract tests (Wave 0)."""

from cellxp.domain.artifacts import ArtifactRef
from cellxp.domain.clock import utc_now_iso
from cellxp.domain.enums import ArtifactType


def test_artifact_ref_defaults():
    a = ArtifactRef(type=ArtifactType.GENOME_TRACK, title="AlphaGenome delta track")
    assert a.id
    assert a.actionable is False
    assert a.summary == {} and a.evidence_ids == []
    assert a.created_at.endswith("+00:00")


def test_artifact_ref_unique_ids_and_independent_defaults():
    a = ArtifactRef(type=ArtifactType.REPORT, title="r1")
    b = ArtifactRef(type=ArtifactType.REPORT, title="r2")
    a.summary["k"] = 1
    assert a.id != b.id
    assert b.summary == {}  # default_factory, not shared


def test_artifact_ref_roundtrips_json():
    a = ArtifactRef(
        type=ArtifactType.GUIDE_TABLE,
        title="CRISPR guides",
        actionable=True,
        evidence_ids=["e1", "e2"],
        storage_ref="cas/sha256/abc",
    )
    assert ArtifactRef.model_validate_json(a.model_dump_json()) == a


def test_utc_now_iso_is_tz_aware():
    assert utc_now_iso().endswith("+00:00")
