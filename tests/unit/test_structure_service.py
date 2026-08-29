"""Unit tests for StructureService and structure transforms (X3, FR-18, STS-1..5)."""

from __future__ import annotations

import pytest
from cellxp.domain.enums import ArtifactType, ConfidenceBand, SequenceAlphabet
from cellxp.domain.evidence import Provenance
from cellxp.domain.models import GenomicInterval
from cellxp.domain.sequences import BiologicalSequence
from cellxp.services.base import ServiceOutcome
from cellxp.services.structure.schemas import (
    ESMFOLD_MAX_RESIDUES,
    ContactMapRequest,
    ContactMapResult,
    DnaShapeRequest,
    DnaShapeResult,
    LigandSpec,
    StructureRequest,
    StructureResult,
)
from cellxp.services.structure.service import StructureService
from cellxp.services.structure.transforms import (
    classify_structure_task,
    low_confidence_spans,
    mean_confidence_band,
    select_structure_model,
    validate_kind_alphabet,
)

# ---------------------------------------------------------------------------
# Helpers / mock backend
# ---------------------------------------------------------------------------


def _protein(seq: str = "MKTAYIAKQR") -> BiologicalSequence:
    return BiologicalSequence(seq=seq, alphabet=SequenceAlphabet.PROTEIN)


def _dna(seq: str = "ACGTACGTAC") -> BiologicalSequence:
    return BiologicalSequence(seq=seq, alphabet=SequenceAlphabet.DNA)


def _interval() -> GenomicInterval:
    return GenomicInterval(chrom="chr1", start=1000, end=2000)


class _MockStructureBackend:
    """Minimal StructureBackend returning canned heavy refs + per-residue confidence."""

    def predict_structure(self, request: StructureRequest) -> StructureResult:
        n = sum(len(s.seq) for s in request.sequences)
        return StructureResult(
            structure_ref="objstore://structures/abc.cif",
            per_residue_confidence=[0.95] * (n - 2) + [0.4, 0.3],
            affinity=-7.2 if request.ligand is not None else None,
            model="boltz2" if request.kind != "protein" else "esmfold",
        )

    def predict_contacts(self, request: ContactMapRequest) -> ContactMapResult:
        return ContactMapResult(
            contacts_ref="objstore://contacts/xyz.npz",
            n_bins=250,
            bin_size_bp=4096,
            model="orca",
        )

    def predict_dna_shape(self, request: DnaShapeRequest) -> DnaShapeResult:
        return DnaShapeResult(
            shape_track_ref="objstore://shape/mgw.bw",
            features=["MGW", "Roll", "ProT", "HelT"],
            model="dnashaper",
        )


# ---------------------------------------------------------------------------
# Transforms — classification
# ---------------------------------------------------------------------------


class TestClassifyStructureTask:
    def test_single_protein_is_protein(self):
        assert classify_structure_task(sequences=[_protein()], interval=None) == "protein"

    def test_two_proteins_is_complex(self):
        assert (
            classify_structure_task(sequences=[_protein(), _protein()], interval=None)
            == "complex"
        )

    def test_protein_with_ligand_is_complex(self):
        assert (
            classify_structure_task(sequences=[_protein()], interval=None, has_ligand=True)
            == "complex"
        )

    def test_dna_is_nucleic_acid(self):
        assert classify_structure_task(sequences=[_dna()], interval=None) == "nucleic_acid"

    def test_interval_only_is_contacts(self):
        assert classify_structure_task(sequences=[], interval=_interval()) == "contacts"

    def test_hint_overrides(self):
        assert (
            classify_structure_task(sequences=[], interval=_interval(), hint="dna_shape")
            == "dna_shape"
        )

    def test_invalid_hint_ignored(self):
        assert (
            classify_structure_task(sequences=[_protein()], interval=None, hint="bogus")
            == "protein"
        )

    def test_no_inputs_returns_none(self):
        assert classify_structure_task(sequences=[], interval=None) is None


# ---------------------------------------------------------------------------
# Transforms — model selection
# ---------------------------------------------------------------------------


class TestSelectStructureModel:
    def test_monomer_protein_is_esmfold(self):
        assert select_structure_model("protein", n_chains=1, has_ligand=False) == "esmfold"

    def test_complex_is_boltz2(self):
        assert select_structure_model("complex", n_chains=2, has_ligand=False) == "boltz2"

    def test_ligand_forces_boltz2(self):
        assert select_structure_model("protein", n_chains=1, has_ligand=True) == "boltz2"

    def test_multichain_forces_boltz2(self):
        assert select_structure_model("protein", n_chains=3, has_ligand=False) == "boltz2"

    def test_nucleic_acid_is_boltz2(self):
        assert select_structure_model("nucleic_acid", n_chains=1, has_ligand=False) == "boltz2"


# ---------------------------------------------------------------------------
# Transforms — confidence derivation
# ---------------------------------------------------------------------------


class TestConfidenceTransforms:
    def test_low_confidence_spans_basic(self):
        spans = low_confidence_spans([0.9, 0.4, 0.3, 0.95, 0.2])
        assert [(s.start, s.end) for s in spans] == [(1, 3), (4, 5)]

    def test_low_confidence_spans_trailing_run(self):
        spans = low_confidence_spans([0.95, 0.95, 0.5, 0.5])
        assert [(s.start, s.end) for s in spans] == [(2, 4)]

    def test_low_confidence_spans_none_low(self):
        assert low_confidence_spans([0.9, 0.95, 0.99]) == []

    def test_mean_band_high(self):
        assert mean_confidence_band([0.95, 0.92]) is ConfidenceBand.HIGH

    def test_mean_band_medium(self):
        assert mean_confidence_band([0.8, 0.7]) is ConfidenceBand.MEDIUM

    def test_mean_band_low(self):
        assert mean_confidence_band([0.4, 0.3]) is ConfidenceBand.LOW

    def test_mean_band_unknown_when_empty(self):
        assert mean_confidence_band([]) is ConfidenceBand.UNKNOWN


class TestValidateKindAlphabet:
    def test_protein_with_protein_ok(self):
        assert validate_kind_alphabet("protein", [_protein()]) is None

    def test_protein_with_dna_errors(self):
        assert validate_kind_alphabet("protein", [_dna()]) is not None

    def test_nucleic_acid_with_protein_errors(self):
        assert validate_kind_alphabet("nucleic_acid", [_protein()]) is not None

    def test_protein_empty_errors(self):
        assert validate_kind_alphabet("protein", []) is not None


# ---------------------------------------------------------------------------
# Service — predict_structure
# ---------------------------------------------------------------------------


class TestPredictStructureNoBackend:
    def test_no_backend_returns_unsupported(self):
        result = StructureService().predict_structure(
            StructureRequest(kind="protein", sequences=[_protein()])
        )
        assert result.outcome is ServiceOutcome.UNSUPPORTED

    def test_unsupported_carries_step(self):
        result = StructureService().predict_structure(
            StructureRequest(kind="protein", sequences=[_protein()])
        )
        assert len(result.steps) >= 1

    def test_unknown_organism_unsupported(self):
        result = StructureService().predict_structure(
            StructureRequest(kind="protein", sequences=[_protein()], organism="Martian")
        )
        assert result.outcome is ServiceOutcome.UNSUPPORTED

    def test_alphabet_mismatch_is_failure(self):
        result = StructureService().predict_structure(
            StructureRequest(kind="nucleic_acid", sequences=[_protein()])
        )
        assert result.outcome is ServiceOutcome.FAILURE
        assert result.error is not None
        assert len(result.steps) >= 1

    def test_oversized_esmfold_sequence_is_failure(self):
        big = _protein("M" + "A" * (ESMFOLD_MAX_RESIDUES + 5))
        result = StructureService().predict_structure(
            StructureRequest(kind="protein", sequences=[big])
        )
        assert result.outcome is ServiceOutcome.FAILURE
        assert "ESMFold limit" in result.error.message

    def test_http_backend_requires_service_url(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv("STRUCTURE_BACKEND", "http")
        monkeypatch.delenv("STRUCTURE_SERVICE_URL", raising=False)
        with pytest.raises(ValueError, match="STRUCTURE_SERVICE_URL"):
            StructureService()

    def test_http_backend_is_selected_from_environment(self, monkeypatch: pytest.MonkeyPatch):
        from cellxp.services.structure.backends import RemoteStructureBackend

        monkeypatch.setenv("STRUCTURE_BACKEND", "http")
        monkeypatch.setenv("STRUCTURE_SERVICE_URL", "http://structure-worker:8102")
        service = StructureService()
        assert isinstance(service._backend, RemoteStructureBackend)


class TestPredictStructureWithBackend:
    def _svc(self) -> StructureService:
        return StructureService(structure_backend=_MockStructureBackend())

    def test_protein_returns_ok(self):
        result = self._svc().predict_structure(
            StructureRequest(kind="protein", sequences=[_protein()])
        )
        assert result.outcome is ServiceOutcome.OK

    def test_structure_ref_present(self):
        result = self._svc().predict_structure(
            StructureRequest(kind="protein", sequences=[_protein()])
        )
        assert result.value.structure_ref is not None

    def test_artifact_is_structure_3d(self):
        result = self._svc().predict_structure(
            StructureRequest(kind="protein", sequences=[_protein()])
        )
        assert len(result.artifacts) == 1
        assert result.artifacts[0].type is ArtifactType.STRUCTURE_3D
        assert result.artifacts[0].storage_ref is not None
        assert result.artifacts[0].actionable is False

    def test_low_confidence_regions_derived(self):
        result = self._svc().predict_structure(
            StructureRequest(kind="protein", sequences=[_protein()])
        )
        # last two residues are 0.4 / 0.3 → one trailing low-confidence span
        assert len(result.value.low_confidence_regions) == 1

    def test_confidence_band_present(self):
        result = self._svc().predict_structure(
            StructureRequest(kind="protein", sequences=[_protein()])
        )
        assert result.value.confidence.band is not None

    def test_evidence_emitted(self):
        result = self._svc().predict_structure(
            StructureRequest(kind="protein", sequences=[_protein()])
        )
        assert len(result.evidence) >= 1

    def test_complex_with_ligand_returns_affinity(self):
        result = self._svc().predict_structure(
            StructureRequest(
                kind="complex",
                sequences=[_protein(), _protein()],
                ligand=LigandSpec(format="smiles", value="CCO"),
            )
        )
        assert result.value.affinity is not None

    def test_provenance_records_model(self):
        result = self._svc().predict_structure(
            StructureRequest(kind="protein", sequences=[_protein()])
        )
        assert result.value.provenance.tool == "esmfold"

    def test_provenance_records_input_and_output_hashes(self):
        backend = _MockStructureBackend()
        raw_predict = backend.predict_structure

        def predict(request: StructureRequest) -> StructureResult:
            raw = raw_predict(request)
            return raw.model_copy(
                update={
                    "structure_ref": "cas/" + "a" * 64,
                    "provenance": Provenance(tool_version="pinned-revision"),
                }
            )

        backend.predict_structure = predict  # type: ignore[method-assign]
        result = StructureService(structure_backend=backend).predict_structure(
            StructureRequest(kind="protein", sequences=[_protein()])
        )
        assert result.value.provenance.input_hash is not None
        assert result.value.provenance.output_hash == "a" * 64
        assert result.steps[0].tool_version == "pinned-revision"
        assert result.steps[0].output_ref == result.value.structure_ref


# ---------------------------------------------------------------------------
# Service — predict_contacts / predict_dna_shape
# ---------------------------------------------------------------------------


class TestPredictContacts:
    def test_no_backend_unsupported(self):
        result = StructureService().predict_contacts(
            ContactMapRequest(interval=_interval(), organism="Homo sapiens", assembly="GRCh38")
        )
        assert result.outcome is ServiceOutcome.UNSUPPORTED

    def test_unknown_assembly_unsupported(self):
        result = StructureService(structure_backend=_MockStructureBackend()).predict_contacts(
            ContactMapRequest(interval=_interval(), organism="Homo sapiens", assembly="NOPE")
        )
        assert result.outcome is ServiceOutcome.UNSUPPORTED

    def test_with_backend_emits_contact_map_artifact(self):
        result = StructureService(structure_backend=_MockStructureBackend()).predict_contacts(
            ContactMapRequest(interval=_interval(), organism="Homo sapiens", assembly="GRCh38")
        )
        assert result.outcome is ServiceOutcome.OK
        assert result.artifacts[0].type is ArtifactType.CONTACT_MAP


class TestPredictDnaShape:
    def test_no_backend_unsupported(self):
        result = StructureService().predict_dna_shape(
            DnaShapeRequest(interval=_interval(), organism="Homo sapiens", assembly="GRCh38")
        )
        assert result.outcome is ServiceOutcome.UNSUPPORTED

    def test_with_backend_emits_genome_track_artifact(self):
        result = StructureService(structure_backend=_MockStructureBackend()).predict_dna_shape(
            DnaShapeRequest(interval=_interval(), organism="Homo sapiens", assembly="GRCh38")
        )
        assert result.outcome is ServiceOutcome.OK
        assert result.artifacts[0].type is ArtifactType.GENOME_TRACK
        assert result.value.features == ["MGW", "Roll", "ProT", "HelT"]

    def test_prokaryote_assembly_supported(self):
        result = StructureService(structure_backend=_MockStructureBackend()).predict_dna_shape(
            DnaShapeRequest(
                interval=GenomicInterval(chrom="NC_000913.3", start=100, end=500),
                organism="Escherichia coli",
                assembly="GCF_000005845.2",
            )
        )
        assert result.outcome is ServiceOutcome.OK


# ---------------------------------------------------------------------------
# PROV-1: every operation records >=1 Step
# ---------------------------------------------------------------------------


class TestProvenanceCoverage:
    @pytest.mark.parametrize("with_backend", [False, True])
    def test_predict_structure_records_step(self, with_backend):
        svc = StructureService(
            structure_backend=_MockStructureBackend() if with_backend else None
        )
        result = svc.predict_structure(
            StructureRequest(kind="protein", sequences=[_protein()])
        )
        assert len(result.steps) >= 1

    @pytest.mark.parametrize("with_backend", [False, True])
    def test_predict_contacts_records_step(self, with_backend):
        svc = StructureService(
            structure_backend=_MockStructureBackend() if with_backend else None
        )
        result = svc.predict_contacts(
            ContactMapRequest(interval=_interval(), organism="Homo sapiens", assembly="GRCh38")
        )
        assert len(result.steps) >= 1
