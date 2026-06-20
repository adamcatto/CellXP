"""Unit tests for the structure subgraph (X3, FR-18, FR-24).

Uses injectable mock backends so no real model calls happen. Covers: protein/complex/NA
routing, genomic contacts + shape, no-input failure, invalid-assembly failure, and
Steps-on-all-paths (FR-24 run-trace compliance).
"""

from __future__ import annotations

from typing import Any

from cellxp.agent.state import (
    AgentState,
    ExecutionCursor,
    NormalizedInputs,
    Subtask,
)
from cellxp.agent.subgraphs.structure import build_subgraph
from cellxp.domain.enums import SequenceAlphabet, SubtaskType, TaskStatus
from cellxp.domain.models import GenomicInterval
from cellxp.domain.sequences import BiologicalSequence
from cellxp.services.structure.schemas import (
    ContactMapRequest,
    ContactMapResult,
    DnaShapeRequest,
    DnaShapeResult,
    StructureRequest,
    StructureResult,
)
from cellxp.services.structure.service import StructureService


# ---------------------------------------------------------------------------
# Mock backend
# ---------------------------------------------------------------------------


class _MockStructureBackend:
    def predict_structure(self, request: StructureRequest) -> StructureResult:
        n = sum(len(s.seq) for s in request.sequences)
        return StructureResult(
            structure_ref="objstore://s/x.cif",
            per_residue_confidence=[0.9] * n,
            model="esmfold",
        )

    def predict_contacts(self, request: ContactMapRequest) -> ContactMapResult:
        return ContactMapResult(contacts_ref="objstore://c/x.npz", n_bins=10, model="orca")

    def predict_dna_shape(self, request: DnaShapeRequest) -> DnaShapeResult:
        return DnaShapeResult(
            shape_track_ref="objstore://sh/x.bw", features=["MGW"], model="dnashaper"
        )


# ---------------------------------------------------------------------------
# State builders
# ---------------------------------------------------------------------------


def _subtask() -> Subtask:
    return Subtask(type=SubtaskType.STRUCTURE, capability="structure", status=TaskStatus.RUNNING)


def _state(inputs: NormalizedInputs, subtask: Subtask | None = None) -> AgentState:
    sub = subtask or _subtask()
    cursor = ExecutionCursor(active_subtask_id=sub.id)
    return AgentState(
        user_query="predict this structure",
        subtasks=[sub.model_dump()],
        cursor=cursor.model_dump(),
        normalized_inputs=inputs.model_dump(),
        evidence=[],
        artifacts=[],
        steps=[],
        errors=[],
    )


def _protein_inputs() -> NormalizedInputs:
    return NormalizedInputs(
        organism="Homo sapiens",
        sequences=[BiologicalSequence(seq="MKTAYIAKQR", alphabet=SequenceAlphabet.PROTEIN)],
    )


def _status(result: dict[str, Any]) -> TaskStatus:
    return Subtask.model_validate(result["subtasks"][0]).status


def _step_names(result: dict[str, Any]) -> list[str]:
    return [s.name if hasattr(s, "name") else s["name"] for s in result["steps"]]


# ---------------------------------------------------------------------------
# Dev mode (no backend)
# ---------------------------------------------------------------------------


class TestSubgraphNoBackend:
    def test_protein_completes_without_backend(self):
        result = build_subgraph()(_state(_protein_inputs()))
        # UNSUPPORTED from the service is a non-error path; subtask still completes.
        assert _status(result) is TaskStatus.DONE

    def test_steps_recorded_without_backend(self):
        result = build_subgraph()(_state(_protein_inputs()))
        assert "classify_structure_task" in _step_names(result)
        assert "call_structure_oracle" in _step_names(result)

    def test_no_inputs_fails_subtask(self):
        result = build_subgraph()(_state(NormalizedInputs(organism="Homo sapiens")))
        assert _status(result) is TaskStatus.FAILED
        assert result.get("errors")

    def test_no_active_subtask_returns_empty(self):
        state = AgentState(
            subtasks=[],
            cursor=ExecutionCursor().model_dump(),
            normalized_inputs=NormalizedInputs().model_dump(),
        )
        assert build_subgraph()(state) == {}


# ---------------------------------------------------------------------------
# With mock backend
# ---------------------------------------------------------------------------


class TestSubgraphWithBackend:
    def _node(self) -> Any:
        return build_subgraph(
            structure_service=StructureService(structure_backend=_MockStructureBackend())
        )

    def test_protein_produces_structure_artifact(self):
        result = self._node()(_state(_protein_inputs()))
        assert _status(result) is TaskStatus.DONE
        assert len(result.get("artifacts", [])) == 1

    def test_protein_emits_evidence(self):
        result = self._node()(_state(_protein_inputs()))
        assert len(result.get("evidence", [])) >= 1

    def test_complex_routes_via_two_chains(self):
        inputs = NormalizedInputs(
            organism="Homo sapiens",
            sequences=[
                BiologicalSequence(seq="MKTAYIAK", alphabet=SequenceAlphabet.PROTEIN),
                BiologicalSequence(seq="GGSGGSGG", alphabet=SequenceAlphabet.PROTEIN),
            ],
        )
        result = self._node()(_state(inputs))
        assert _status(result) is TaskStatus.DONE

    def test_genomic_contacts_path(self):
        inputs = NormalizedInputs(
            organism="Homo sapiens",
            assembly="GRCh38",
            intervals=[GenomicInterval(chrom="chr1", start=1000, end=2000)],
        )
        result = self._node()(_state(inputs))
        assert _status(result) is TaskStatus.DONE
        assert "validate_reference" in _step_names(result)
        assert len(result.get("artifacts", [])) == 1

    def test_dna_shape_via_hint(self):
        sub = _subtask()
        sub.inputs = {"kind": "dna_shape"}
        inputs = NormalizedInputs(
            organism="Homo sapiens",
            assembly="GRCh38",
            intervals=[GenomicInterval(chrom="chr1", start=1000, end=2000)],
        )
        result = self._node()(_state(inputs, subtask=sub))
        assert _status(result) is TaskStatus.DONE


# ---------------------------------------------------------------------------
# Failure / invalid paths
# ---------------------------------------------------------------------------


class TestSubgraphInvalidPaths:
    def test_genomic_without_assembly_fails(self):
        sub = _subtask()
        sub.inputs = {"kind": "contacts"}
        inputs = NormalizedInputs(
            organism="Homo sapiens",
            intervals=[GenomicInterval(chrom="chr1", start=1000, end=2000)],
        )
        result = build_subgraph()(_state(inputs, subtask=sub))
        assert _status(result) is TaskStatus.FAILED
        assert result.get("errors")

    def test_unknown_assembly_fails_at_validation(self):
        inputs = NormalizedInputs(
            organism="Homo sapiens",
            assembly="NOPE",
            intervals=[GenomicInterval(chrom="chr1", start=1000, end=2000)],
        )
        result = build_subgraph()(_state(inputs))
        assert _status(result) is TaskStatus.FAILED
        assert "validate_reference" in _step_names(result)

    def test_alphabet_mismatch_fails_subtask(self):
        # request nucleic_acid kind but supply a protein chain via hint
        sub = _subtask()
        sub.inputs = {"kind": "nucleic_acid"}
        inputs = NormalizedInputs(
            organism="Homo sapiens",
            sequences=[BiologicalSequence(seq="MKTAYIAK", alphabet=SequenceAlphabet.PROTEIN)],
        )
        node = build_subgraph(
            structure_service=StructureService(structure_backend=_MockStructureBackend())
        )
        result = node(_state(inputs, subtask=sub))
        assert _status(result) is TaskStatus.FAILED
        assert result.get("errors")


# ---------------------------------------------------------------------------
# FR-24: run-trace completeness
# ---------------------------------------------------------------------------


class TestRunTraceCompleteness:
    def test_success_path_has_steps(self):
        node = build_subgraph(
            structure_service=StructureService(structure_backend=_MockStructureBackend())
        )
        result = node(_state(_protein_inputs()))
        assert len(result.get("steps", [])) >= 2

    def test_failure_path_has_steps(self):
        result = build_subgraph()(_state(NormalizedInputs(organism="Homo sapiens")))
        assert len(result.get("steps", [])) >= 1
