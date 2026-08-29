"""Artifact contract tests (Wave 0)."""

import pytest
from cellxp.domain.artifacts import (
    OBJECT_INLINE_MAX,
    AccessibilityMetadata,
    ArtifactManifest,
    ArtifactRef,
    CoordinateFrame,
    ExportDescriptor,
    Interaction,
)
from cellxp.domain.clock import utc_now_iso
from cellxp.domain.enums import ArtifactType, CoordinateSystem
from pydantic import ValidationError


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


def test_artifact_ref_rejects_oversized_summary():
    with pytest.raises(ValidationError, match="OBJECT_INLINE_MAX"):
        ArtifactRef(
            type=ArtifactType.REPORT,
            title="Too large for agent state",
            summary={"text": "x" * OBJECT_INLINE_MAX},
        )


def test_utc_now_iso_is_tz_aware():
    assert utc_now_iso().endswith("+00:00")


def test_artifact_manifest_roundtrips_and_compacts_to_ref():
    manifest = ArtifactManifest(
        type=ArtifactType.GENOME_TRACK,
        payload_schema="cellxp.genome_track/1.0",
        title="Regulatory delta",
        status="ready",
        revision=1,
        session_id="session-1",
        run_id="run-1",
        evidence_ids=["evidence-1"],
        payload={"schema": "genome_track", "version": "1.0", "data": []},
        coordinate_frame=CoordinateFrame(
            kind="genomic",
            organism="Homo sapiens",
            assembly="GRCh38",
            contig="chr1",
            convention="0-based-half-open",
        ),
        exports=[ExportDescriptor(format="bedGraph", media_type="text/plain", kind="data")],
        accessibility=AccessibilityMetadata(summary="No material delta in this interval."),
    )

    assert ArtifactManifest.model_validate_json(manifest.model_dump_json()) == manifest
    assert manifest.to_ref().model_dump() == {
        "id": manifest.id,
        "type": ArtifactType.GENOME_TRACK,
        "title": manifest.title,
        "subtask_id": None,
        "storage_ref": None,
        "summary": {},
        "evidence_ids": ["evidence-1"],
        "actionable": False,
        "created_at": manifest.created_at,
    }


def test_genomic_coordinate_frame_requires_explicit_context():
    with pytest.raises(ValidationError, match="assembly, contig, convention"):
        CoordinateFrame(kind="genomic", organism="Homo sapiens")


def test_genomic_coordinate_frame_requires_canonical_convention():
    with pytest.raises(ValidationError, match="must use 0-based-half-open"):
        CoordinateFrame(
            kind="genomic",
            organism="Homo sapiens",
            assembly="GRCh38",
            contig="chr1",
            convention=CoordinateSystem.ONE_BASED_INCLUSIVE,
        )


def test_structure_coordinate_frame_requires_chain_mapping():
    with pytest.raises(ValidationError, match="non-empty chain_map"):
        CoordinateFrame(kind="structure")


def test_ready_manifest_requires_payload_reference():
    with pytest.raises(ValidationError, match="inline payload or storage_ref"):
        ArtifactManifest(
            type=ArtifactType.REPORT,
            payload_schema="cellxp.report/1.0",
            title="Report",
            status="ready",
            session_id="session-1",
            run_id="run-1",
            accessibility=AccessibilityMetadata(summary="Report summary"),
        )


def test_actionable_manifest_requires_review_status():
    with pytest.raises(ValidationError, match="explicit review status"):
        ArtifactManifest(
            type=ArtifactType.GUIDE_TABLE,
            payload_schema="cellxp.guide_table/1.0",
            title="Candidate guides",
            session_id="session-1",
            run_id="run-1",
            actionable=True,
            accessibility=AccessibilityMetadata(summary="Candidate guide table"),
        )


def test_manifest_rejects_oversized_inline_payload():
    with pytest.raises(ValidationError, match="OBJECT_INLINE_MAX"):
        ArtifactManifest(
            type=ArtifactType.FILE,
            payload_schema="cellxp.file/1.0",
            title="Too large",
            session_id="session-1",
            run_id="run-1",
            payload={"data": "x" * OBJECT_INLINE_MAX},
            accessibility=AccessibilityMetadata(summary="File"),
        )


def test_manifest_requires_versioned_payload_envelope():
    with pytest.raises(ValidationError, match="version, data"):
        ArtifactManifest(
            type=ArtifactType.REPORT,
            payload_schema="cellxp.report/1.0",
            title="Incomplete payload",
            session_id="session-1",
            run_id="run-1",
            payload={"schema": "report"},
            accessibility=AccessibilityMetadata(summary="Report"),
        )


def test_interactive_manifest_requires_data_export_and_accessible_fallback():
    base = {
        "type": ArtifactType.GENOME_TRACK,
        "payload_schema": "cellxp.genome_track/1.0",
        "title": "Track",
        "session_id": "session-1",
        "run_id": "run-1",
        "interactions": [Interaction(type="zoom")],
        "accessibility": AccessibilityMetadata(summary="Track summary"),
    }
    with pytest.raises(ValidationError, match="underlying-data export"):
        ArtifactManifest(**base)

    base["exports"] = [ExportDescriptor(format="bed", media_type="text/plain", kind="data")]
    with pytest.raises(ValidationError, match="tabular or static fallback"):
        ArtifactManifest(**base)


def test_manifest_cannot_supersede_itself():
    with pytest.raises(ValidationError, match="cannot supersede itself"):
        ArtifactManifest(
            id="artifact-1",
            type=ArtifactType.REPORT,
            payload_schema="cellxp.report/1.0",
            title="Correction",
            session_id="session-1",
            run_id="run-1",
            supersedes="artifact-1",
            accessibility=AccessibilityMetadata(summary="Report"),
        )
