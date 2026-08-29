"""Unit coverage for the X1 GWAS/QTL subgraph (FR-14, RGS-1, PROV-1)."""

from __future__ import annotations

from cellxp.agent.state import AgentState, ExecutionCursor, NormalizedInputs, Subtask
from cellxp.agent.subgraphs.gwas import build_subgraph
from cellxp.domain.enums import ConfidenceBand, SubtaskType, TaskStatus
from cellxp.domain.evidence import Confidence
from cellxp.domain.models import GenomicInterval, Variant
from cellxp.services.gwas import Association, GwasRequest, GwasResult, GwasService


class _Backend:
    def lookup_associations(self, request: GwasRequest) -> GwasResult:
        return GwasResult(
            associations=[
                Association(
                    trait="height",
                    p_value=1e-10,
                    study_accession="GCST1",
                    citations=["PMID:1"],
                    source="GWAS Catalog",
                    source_release="2026-05",
                )
            ],
            confidence=Confidence(band=ConfidenceBand.HIGH),
            storage_ref="objects/gwas/table.parquet",
            locus_plot_ref="objects/gwas/locus.json",
        )

    def compute_ld(self, request):
        raise NotImplementedError

    def fine_map(self, request):
        raise NotImplementedError

    def coloc(self, request):
        raise NotImplementedError


class _ComposedBackend(_Backend):
    def __init__(self) -> None:
        self.operations: list[str] = []

    def compute_ld(self, request):
        from cellxp.services.gwas import LdPair, LdResult
        self.operations.append("ld")
        return LdResult(pairs=[LdPair(variant_a="rs1", variant_b="rs2", r2=.8)],
                        population=request.population, panel="fixture")

    def fine_map(self, request):
        from cellxp.services.gwas import CredibleSet, CredibleVariant, FineMapResult
        self.operations.append("fine-map")
        return FineMapResult(credible_sets=[CredibleSet(
            id="cs1", variants=[CredibleVariant(variant_id="rs1", pip=.8)],
            region=request.interval, coverage=.95,
        )], assumptions=["fixture"], input_datasets=[request.summary_stats_ref])

    def coloc(self, request):
        from cellxp.services.gwas import ColocBatchResult, ColocResult
        self.operations.append("coloc")
        return ColocBatchResult(results=[ColocResult(
            trait=request.trait, tissue=request.tissues[0], h4=.9,
            gwas_dataset=request.gwas_stats_ref, qtl_dataset=request.qtl_stats_ref,
        )])


def _subtask(**inputs: object) -> Subtask:
    return Subtask(
        type=SubtaskType.GWAS,
        capability="gwas",
        status=TaskStatus.RUNNING,
        inputs=inputs,
    )


def _state(normalized: NormalizedInputs, subtask: Subtask | None = None) -> AgentState:
    active = subtask or _subtask()
    return AgentState(
        subtasks=[active.model_dump()],
        cursor=ExecutionCursor(active_subtask_id=active.id).model_dump(),
        normalized_inputs=normalized.model_dump(),
        evidence=[],
        artifacts=[],
        steps=[],
        errors=[],
    )


def _human_variant() -> Variant:
    return Variant(chrom="chr1", pos=999, ref="A", alt="T", assembly="GRCh38")


def test_no_subject_fails_with_step() -> None:
    result = build_subgraph()(
        _state(NormalizedInputs(organism="Homo sapiens", assembly="GRCh38"))
    )
    assert Subtask.model_validate(result["subtasks"][0]).status is TaskStatus.FAILED
    assert result["steps"]
    assert result["errors"]


def test_missing_coordinate_context_fails() -> None:
    result = build_subgraph()(_state(NormalizedInputs(variants=[_human_variant()])))
    assert Subtask.model_validate(result["subtasks"][0]).status is TaskStatus.FAILED
    assert result["steps"]


def test_valid_variant_path_emits_evidence_artifacts_and_all_pipeline_steps() -> None:
    node = build_subgraph(gwas_service=GwasService(backend=_Backend()))
    result = node(
        _state(
            NormalizedInputs(
                organism="Homo sapiens", assembly="GRCh38", variants=[_human_variant()]
            ),
            _subtask(traits=["height"], do_coloc=False),
        )
    )
    assert Subtask.model_validate(result["subtasks"][0]).status is TaskStatus.DONE
    assert result["evidence"]
    assert len(result["artifacts"]) == 2
    names = {step.name for step in result["steps"]}
    assert {"resolve_gwas_subject", "query_gwas_evidence", "rank_and_emit_locus"} <= names
    assert all(step.started_at and step.finished_at for step in result["steps"])


def test_valid_interval_is_reference_validated_without_sequence_backend() -> None:
    interval = GenomicInterval(
        species="Homo sapiens", assembly="GRCh38", chrom="chr1", start=900, end=1_100
    )
    node = build_subgraph(gwas_service=GwasService(backend=_Backend()))
    result = node(
        _state(
            NormalizedInputs(
                organism="Homo sapiens", assembly="GRCh38", intervals=[interval]
            )
        )
    )
    assert Subtask.model_validate(result["subtasks"][0]).status is TaskStatus.DONE
    assert any(step.name == "get_sequence" for step in result["steps"])


def test_out_of_bounds_variant_fails_before_gwas_backend() -> None:
    bad = Variant(chrom="chr22", pos=60_000_000, ref="A", alt="T", assembly="GRCh38")
    node = build_subgraph(gwas_service=GwasService(backend=_Backend()))
    result = node(
        _state(
            NormalizedInputs(organism="Homo sapiens", assembly="GRCh38", variants=[bad])
        )
    )
    assert Subtask.model_validate(result["subtasks"][0]).status is TaskStatus.FAILED
    assert result["errors"][0].kind == "ValidationError"
    assert all(step.started_at and step.finished_at for step in result["steps"])


def test_invalid_interval_fails_before_gwas_backend() -> None:
    bad = GenomicInterval(chrom="chr1", start=1_000, end=900, assembly="GRCh38")
    node = build_subgraph(gwas_service=GwasService(backend=_Backend()))
    result = node(
        _state(
            NormalizedInputs(
                organism="Homo sapiens", assembly="GRCh38", intervals=[bad]
            )
        )
    )
    assert Subtask.model_validate(result["subtasks"][0]).status is TaskStatus.FAILED
    assert result["errors"]


def test_unknown_interval_contig_fails_before_gwas_backend() -> None:
    bad = GenomicInterval(chrom="chr404", start=100, end=200, assembly="GRCh38")
    node = build_subgraph(gwas_service=GwasService(backend=_Backend()))
    result = node(
        _state(
            NormalizedInputs(
                organism="Homo sapiens", assembly="GRCh38", intervals=[bad]
            )
        )
    )
    assert Subtask.model_validate(result["subtasks"][0]).status is TaskStatus.FAILED
    assert result["errors"][0].kind == "ValidationError"


def test_no_backend_is_honest_done_path_with_steps() -> None:
    result = build_subgraph()(
        _state(
            NormalizedInputs(
                organism="Homo sapiens", assembly="GRCh38", variants=[_human_variant()]
            )
        )
    )
    assert Subtask.model_validate(result["subtasks"][0]).status is TaskStatus.DONE
    assert result["steps"]
    assert "errors" not in result


def test_non_human_coverage_unavailable_is_done_not_mismatched() -> None:
    mouse = Variant(chrom="chr1", pos=999, ref="A", alt="T", assembly="GRCm39")
    node = build_subgraph(gwas_service=GwasService(backend=_Backend()))
    result = node(
        _state(
            NormalizedInputs(organism="Mus musculus", assembly="GRCm39", variants=[mouse])
        )
    )
    assert Subtask.model_validate(result["subtasks"][0]).status is TaskStatus.DONE
    assert not result["evidence"]


def test_gene_identifier_without_reference_backend_fails_explicitly() -> None:
    result = build_subgraph()(
        _state(
            NormalizedInputs(
                organism="Homo sapiens", assembly="GRCh38", identifiers=["LDLR"]
            )
        )
    )
    assert Subtask.model_validate(result["subtasks"][0]).status is TaskStatus.FAILED
    assert result["errors"][0].kind == "UnsupportedReference"


def test_no_active_subtask_returns_empty_update() -> None:
    state = AgentState(
        subtasks=[],
        cursor=ExecutionCursor().model_dump(),
        normalized_inputs=NormalizedInputs().model_dump(),
    )
    assert build_subgraph()(state) == {}


def test_requested_statistical_operations_execute_and_preserve_partial_success() -> None:
    backend = _ComposedBackend()
    node = build_subgraph(gwas_service=GwasService(backend=backend))
    result = node(_state(
        NormalizedInputs(organism="Homo sapiens", assembly="GRCh38", variants=[_human_variant()]),
        _subtask(
            traits=["height"], tissues=["liver"], ld_population="EUR",
            do_finemap=True, summary_stats_ref="stats", ld_matrix_ref="ld",
            do_coloc=True, gwas_stats_ref="gwas", qtl_stats_ref="qtl",
        ),
    ))
    assert backend.operations == ["ld", "fine-map", "coloc"]
    assert Subtask.model_validate(result["subtasks"][0]).status is TaskStatus.DONE
    assert "errors" not in result
