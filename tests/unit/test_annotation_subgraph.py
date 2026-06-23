"""Unit tests for the annotation subgraph (L1, FR-16, FR-24)."""

from __future__ import annotations

from typing import Any

from cellxp.agent.state import (
    AgentState,
    ExecutionCursor,
    NormalizedInputs,
    RawInput,
    Subtask,
)
from cellxp.agent.subgraphs.annotation import build_subgraph
from cellxp.domain.enums import SequenceAlphabet, Strand, SubtaskType, TaskStatus
from cellxp.domain.models import GenomicInterval
from cellxp.domain.sequences import BiologicalSequence
from cellxp.services.base import ServiceOutcome, ServiceResult
from cellxp.services.reference import EntityResolveRequest, EntityResolveResult, ResolvedEntity
from cellxp.services.reference.annotations import (
    AnnotationFeature,
    AnnotationRequest,
    AnnotationResult,
)
from cellxp.services.reference.genome import ReferenceGenomeService


class _AnnotatingReferenceService(ReferenceGenomeService):
    def annotate(self, request: AnnotationRequest) -> ServiceResult[AnnotationResult]:
        return ServiceResult.succeeded(
            AnnotationResult(
                organism=request.organism,
                assembly=request.assembly,
                source_databases=["test_catalog"],
                features=[
                    AnnotationFeature(
                        feature_id="gene-1",
                        feature_type="gene",
                        chrom=request.chrom or "contig_1",
                        start=0,
                        end=1200,
                        name="dnaA",
                        source="test_catalog",
                    )
                ],
            )
        )


class _Snap25ResolvingReferenceService(ReferenceGenomeService):
    def resolve_entity(self, request: EntityResolveRequest) -> ServiceResult[EntityResolveResult]:
        if request.identifier.upper() != "SNAP25":
            return ServiceResult.empty(f"identifier {request.identifier!r} was not found")
        return ServiceResult.succeeded(
            EntityResolveResult(
                entity=ResolvedEntity(
                    identifier="SNAP25",
                    type="gene",
                    label="SNAP25",
                    organism=request.organism,
                    assembly=request.assembly or "GRCh38",
                    chrom="chr20",
                    start=30_000_000,
                    end=30_050_000,
                    strand=Strand.MINUS,
                    refs={"Ensembl": "ENSG00000139318"},
                )
            )
        )

    def annotate(self, request: AnnotationRequest) -> ServiceResult[AnnotationResult]:
        return ServiceResult.succeeded(
            AnnotationResult(
                organism=request.organism,
                assembly=request.assembly,
                source_databases=["test_catalog"],
                features=[
                    AnnotationFeature(
                        feature_id="ENSG00000139318",
                        feature_type="gene",
                        chrom=request.chrom or "chr20",
                        start=request.start or 0,
                        end=request.end or 50_000,
                        name="SNAP25",
                        source="test_catalog",
                    )
                ],
            )
        )


def _state(inputs: NormalizedInputs, *, raw_inputs: list[RawInput] | None = None) -> AgentState:
    subtask = Subtask(
        type=SubtaskType.ANNOTATION,
        capability="annotation",
        status=TaskStatus.RUNNING,
    )
    return AgentState(
        user_query="annotate this region",
        subtasks=[subtask.model_dump()],
        cursor=ExecutionCursor(active_subtask_id=subtask.id).model_dump(),
        normalized_inputs=inputs.model_dump(),
        raw_inputs=[item.model_dump() for item in (raw_inputs or [])],
        evidence=[],
        artifacts=[],
        steps=[],
        errors=[],
    )


def _status(result: dict[str, Any]) -> TaskStatus:
    return Subtask.model_validate(result["subtasks"][0]).status


def _step_names(result: dict[str, Any]) -> set[str]:
    return {step.name if hasattr(step, "name") else step["name"] for step in result["steps"]}


def test_missing_scope_fails_with_step_and_error() -> None:
    result = build_subgraph()(
        _state(NormalizedInputs(organism="Homo sapiens", assembly="GRCh38"))
    )
    assert _status(result) is TaskStatus.FAILED
    assert result["errors"]
    assert "classify_scope" in _step_names(result)


def test_gene_symbol_resolves_to_interval_before_annotation() -> None:
    node = build_subgraph(reference_service=_Snap25ResolvingReferenceService())
    result = node(
        _state(
            NormalizedInputs(
                organism="Homo sapiens",
                assembly="GRCh38",
                identifiers=["SNAP25"],
            )
        )
    )
    assert _status(result) is TaskStatus.DONE
    assert "resolve_gene_locus" in _step_names(result)
    assert {"classify_scope", "validate_reference", "call_annotation"} <= _step_names(result)
    assert result["evidence"]
    assert any("SNAP25" in item.claim for item in result["evidence"])


def test_invalid_assembly_fails_before_annotation_call() -> None:
    result = build_subgraph()(
        _state(
            NormalizedInputs(
                organism="Homo sapiens",
                assembly="FakeAsm",
                intervals=[GenomicInterval(chrom="chr1", start=0, end=1000)],
            )
        )
    )
    assert _status(result) is TaskStatus.FAILED
    assert "validate_reference" in _step_names(result)
    assert "call_annotation" not in _step_names(result)


def test_interval_without_backend_completes_honestly() -> None:
    result = build_subgraph()(
        _state(
            NormalizedInputs(
                organism="Homo sapiens",
                assembly="GRCh38",
                intervals=[GenomicInterval(chrom="chr1", start=0, end=50_000)],
            )
        )
    )
    assert _status(result) is TaskStatus.DONE
    assert not result.get("errors")
    assert {"classify_scope", "validate_reference", "call_annotation"} <= _step_names(result)


def test_pasted_sequence_without_upload_completes_with_deferred_message() -> None:
    result = build_subgraph()(
        _state(
            NormalizedInputs(
                organism="Escherichia coli",
                assembly="GCF_000005845.2",
                sequences=[
                    BiologicalSequence(seq="ATGAAACGCATTAGCACCACC", alphabet=SequenceAlphabet.DNA)
                ],
            )
        )
    )
    assert _status(result) is TaskStatus.DONE
    assert not result.get("errors")
    assert "call_annotation" in _step_names(result)


def test_fasta_upload_dispatches_annotation_request() -> None:
    result = build_subgraph()(
        _state(
            NormalizedInputs(
                organism="Escherichia coli",
                assembly="GCF_000005845.2",
            ),
            raw_inputs=[RawInput(kind="file", file_ref="objstore://fasta/ecoli.fa")],
        )
    )
    assert _status(result) is TaskStatus.DONE
    assert "call_annotation" in _step_names(result)


def test_mock_backend_emits_evidence_and_artifact() -> None:
    node = build_subgraph(reference_service=_AnnotatingReferenceService())
    result = node(
        _state(
            NormalizedInputs(
                organism="Homo sapiens",
                assembly="GRCh38",
                intervals=[GenomicInterval(chrom="chr1", start=0, end=50_000)],
            )
        )
    )
    assert _status(result) is TaskStatus.DONE
    assert result["evidence"]
    assert result["artifacts"]
    assert result["artifacts"][0].type.value == "genome_track"


def test_no_active_subtask_returns_empty() -> None:
    assert build_subgraph()(
        AgentState(
            subtasks=[],
            cursor=ExecutionCursor().model_dump(),
            normalized_inputs=NormalizedInputs().model_dump(),
        )
    ) == {}
