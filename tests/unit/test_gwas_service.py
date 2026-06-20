"""Unit coverage for the X1 GWAS/QTL service (FR-14, GWS-1..5, PROV-1)."""

from __future__ import annotations

import pytest

from cellxp.domain.enums import ConfidenceBand
from cellxp.domain.evidence import Confidence
from cellxp.domain.models import GenomicInterval, Variant
from cellxp.services.base import ServiceOutcome
from cellxp.services.gwas import (
    Association,
    ColocBatchResult,
    ColocRequest,
    ColocResult,
    CredibleSet,
    CredibleVariant,
    FineMapRequest,
    FineMapResult,
    GwasRequest,
    GwasResult,
    GwasService,
    LdPair,
    LdRequest,
    LdResult,
)
from cellxp.services.registry import registry


def _interval() -> GenomicInterval:
    return GenomicInterval(assembly="GRCh38", chrom="chr1", start=900, end=1_100)


def _request() -> GwasRequest:
    return GwasRequest(
        subject=Variant(chrom="chr1", pos=999, ref="A", alt="T", assembly="GRCh38"),
        organism="Homo sapiens",
        assembly="GRCh38",
    )


class _Backend:
    def lookup_associations(self, request: GwasRequest) -> GwasResult:
        return GwasResult(
            associations=[
                Association(
                    trait="LDL cholesterol",
                    variant_id="rs123",
                    beta=0.12,
                    p_value=1e-9,
                    effect_allele="T",
                    study_accession="GCST000001",
                    citations=["PMID:123456"],
                    source="GWAS Catalog",
                    source_release="2026-05",
                    sample_size=100_000,
                )
            ],
            confidence=Confidence(band=ConfidenceBand.HIGH, score=0.9),
            storage_ref="objects/gwas/associations.parquet",
            locus_plot_ref="objects/gwas/locus.json",
        )

    def compute_ld(self, request: LdRequest) -> LdResult:
        return LdResult(
            pairs=[LdPair(variant_a="rs1", variant_b="rs2", r2=0.8)],
            population=request.population,
            panel="1000G",
            assumptions=["matched ancestry panel"],
            storage_ref="objects/gwas/ld.parquet",
        )

    def fine_map(self, request: FineMapRequest) -> FineMapResult:
        return FineMapResult(
            credible_sets=[
                CredibleSet(
                    id="cs1",
                    variants=[CredibleVariant(variant_id="rs1", pip=0.8)],
                    region=request.interval,
                    coverage=0.95,
                )
            ],
            assumptions=["single causal component"],
            input_datasets=[request.summary_stats_ref],
            storage_ref="objects/gwas/finemap.parquet",
        )

    def coloc(self, request: ColocRequest) -> ColocBatchResult:
        return ColocBatchResult(
            results=[
                ColocResult(
                    trait=request.trait,
                    tissue=request.tissues[0],
                    h4=0.91,
                    gwas_dataset=request.gwas_stats_ref,
                    qtl_dataset=request.qtl_stats_ref,
                )
            ],
            assumptions=["one causal variant per trait"],
            input_datasets=[request.gwas_stats_ref, request.qtl_stats_ref],
            storage_ref="objects/gwas/coloc.parquet",
        )


class _EmptyBackend(_Backend):
    def lookup_associations(self, request: GwasRequest) -> GwasResult:
        return GwasResult(
            confidence=Confidence(band=ConfidenceBand.UNKNOWN),
            coverage_note="query ran; no known associations",
        )


class _FailingBackend(_Backend):
    def lookup_associations(self, request: GwasRequest) -> GwasResult:
        raise RuntimeError("upstream unavailable")


def _assert_provenance(result) -> None:  # noqa: ANN001
    assert result.steps
    assert result.steps[0].started_at
    assert result.steps[0].finished_at


def test_service_is_registered() -> None:
    assert registry.get("gwas") is GwasService


@pytest.mark.parametrize(
    ("operation", "operation_request"),
    [
        ("lookup_associations", _request()),
        (
            "compute_ld",
            LdRequest(
                interval=_interval(), organism="Homo sapiens", assembly="GRCh38", population="EUR"
            ),
        ),
        (
            "fine_map",
            FineMapRequest(
                interval=_interval(),
                organism="Homo sapiens",
                assembly="GRCh38",
                trait="LDL",
                summary_stats_ref="objects/summary.tsv",
            ),
        ),
        (
            "coloc",
            ColocRequest(
                interval=_interval(),
                organism="Homo sapiens",
                assembly="GRCh38",
                trait="LDL",
                tissues=["liver"],
                gwas_stats_ref="objects/gwas.tsv",
                qtl_stats_ref="objects/qtl.tsv",
            ),
        ),
    ],
)
def test_no_backend_is_unsupported_with_step(operation: str, operation_request: object) -> None:
    result = getattr(GwasService(), operation)(operation_request)
    assert result.outcome is ServiceOutcome.UNSUPPORTED
    _assert_provenance(result)


def test_non_human_data_is_unsupported() -> None:
    request = GwasRequest(
        subject=Variant(chrom="chr1", pos=999, ref="A", alt="T"),
        organism="Mus musculus",
        assembly="GRCm39",
    )
    result = GwasService(backend=_Backend()).lookup_associations(request)
    assert result.outcome is ServiceOutcome.UNSUPPORTED
    assert "limited/no data" in result.detail
    _assert_provenance(result)


def test_assembly_must_match_organism() -> None:
    request = _request().model_copy(update={"assembly": "GRCm39"})
    result = GwasService(backend=_Backend()).lookup_associations(request)
    assert result.outcome is ServiceOutcome.UNSUPPORTED
    _assert_provenance(result)


def test_unknown_organism_is_unsupported() -> None:
    request = _request().model_copy(update={"organism": "Unknown species"})
    result = GwasService(backend=_Backend()).lookup_associations(request)
    assert result.outcome is ServiceOutcome.UNSUPPORTED
    _assert_provenance(result)


def test_association_lookup_emits_evidence_and_persisted_artifacts() -> None:
    result = GwasService(backend=_Backend()).lookup_associations(_request())
    assert result.outcome is ServiceOutcome.OK
    assert result.evidence[0].provenance.citations == ["PMID:123456", "GCST000001"]
    assert {artifact.storage_ref for artifact in result.artifacts} == {
        "objects/gwas/associations.parquet",
        "objects/gwas/locus.json",
    }
    _assert_provenance(result)


def test_empty_query_is_distinct_from_failure() -> None:
    result = GwasService(backend=_EmptyBackend()).lookup_associations(_request())
    assert result.outcome is ServiceOutcome.EMPTY
    assert result.error is None
    _assert_provenance(result)


def test_backend_exception_is_failure_with_failed_step() -> None:
    result = GwasService(backend=_FailingBackend()).lookup_associations(_request())
    assert result.outcome is ServiceOutcome.FAILURE
    assert result.error.message == "upstream unavailable"
    assert result.steps[0].status.value == "failed"
    _assert_provenance(result)


def test_ld_operation_returns_persisted_matrix() -> None:
    request = LdRequest(
        interval=_interval(), organism="Homo sapiens", assembly="GRCh38", population="EUR"
    )
    result = GwasService(backend=_Backend()).compute_ld(request)
    assert result.outcome is ServiceOutcome.OK
    assert result.value.pairs[0].r2 == 0.8
    assert result.artifacts[0].storage_ref == "objects/gwas/ld.parquet"
    _assert_provenance(result)


def test_fine_map_exposes_assumptions_and_inputs() -> None:
    request = FineMapRequest(
        interval=_interval(),
        organism="Homo sapiens",
        assembly="GRCh38",
        trait="LDL",
        summary_stats_ref="objects/summary.tsv",
    )
    result = GwasService(backend=_Backend()).fine_map(request)
    assert result.outcome is ServiceOutcome.OK
    assert result.value.assumptions
    assert result.value.input_datasets == ["objects/summary.tsv"]
    _assert_provenance(result)


def test_coloc_exposes_assumptions_and_inputs() -> None:
    request = ColocRequest(
        interval=_interval(),
        organism="Homo sapiens",
        assembly="GRCh38",
        trait="LDL",
        tissues=["liver"],
        gwas_stats_ref="objects/gwas.tsv",
        qtl_stats_ref="objects/qtl.tsv",
    )
    result = GwasService(backend=_Backend()).coloc(request)
    assert result.outcome is ServiceOutcome.OK
    assert result.value.assumptions
    assert len(result.value.input_datasets) == 2
    _assert_provenance(result)
