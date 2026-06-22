"""Opt-in live service checks; excluded unless explicitly enabled by environment."""

from __future__ import annotations

import os

import pytest

from cellxp.domain.models import Variant
from cellxp.services.crispr import GuideScoringRequest, crispr_backend_from_environment
from cellxp.services.gwas import GwasRequest, gwas_backend_from_environment
from cellxp.services.gwas import ColocRequest, FineMapRequest, LdRequest
from cellxp.domain.models import GenomicInterval

pytestmark = [pytest.mark.live]


@pytest.mark.skipif(os.getenv("CELLXP_RUN_LIVE_GWAS") != "1",
                    reason="set CELLXP_RUN_LIVE_GWAS=1 and GWAS_BACKEND=ebi")
def test_live_ebi_catalog_lookup() -> None:
    backend = gwas_backend_from_environment()
    assert backend is not None
    result = backend.lookup_associations(GwasRequest(
        subject=Variant(chrom="1", pos=109274967, ref="G", alt="A", assembly="GRCh38",
                        rsid="rs2476601"),
        organism="Homo sapiens", assembly="GRCh38", do_finemap=False, do_coloc=False,
    ))
    assert result.provenance.tool


@pytest.mark.skipif(os.getenv("CELLXP_RUN_LIVE_CRISPR") != "1",
                    reason="set CELLXP_RUN_LIVE_CRISPR=1 and CRISPR_BACKEND=http")
def test_live_crispr_worker_scoring() -> None:
    backend = crispr_backend_from_environment()
    assert backend is not None
    result = backend.score_on_target(GuideScoringRequest(
        guides=["GAGTCCGAGCAGAAGAAGAA"], organism="Homo sapiens", assembly="GRCh38",
    ))
    assert 0 <= result.scores["GAGTCCGAGCAGAAGAAGAA"] <= 1


@pytest.mark.skipif(os.getenv("CELLXP_RUN_LIVE_GWAS_WORKER") != "1",
                    reason="set CELLXP_RUN_LIVE_GWAS_WORKER=1 and GWAS_BACKEND=http")
def test_live_gwas_worker_attestation_and_statistical_pipeline() -> None:
    backend = gwas_backend_from_environment()
    assert backend is not None and hasattr(backend, "attest")
    attestation = backend.attest()
    assert attestation["status"] == "ok"
    interval = GenomicInterval(
        assembly="GRCh38", chrom=os.getenv("CELLXP_GWAS_TEST_CHROM", "chr1"),
        start=int(os.getenv("CELLXP_GWAS_TEST_START", "1000000")),
        end=int(os.getenv("CELLXP_GWAS_TEST_END", "1100000")),
    )
    population = os.getenv("CELLXP_GWAS_TEST_POPULATION", "EUR")
    ld = backend.compute_ld(LdRequest(
        interval=interval, organism="Homo sapiens", assembly="GRCh38", population=population,
    ))
    assert ld.panel and ld.storage_ref and ld.provenance.tool_version

    summary_ref = os.environ["CELLXP_GWAS_TEST_SUMMARY_STATS_REF"]
    ld_ref = os.environ["CELLXP_GWAS_TEST_LD_MATRIX_REF"]
    fine = backend.fine_map(FineMapRequest(
        interval=interval, organism="Homo sapiens", assembly="GRCh38", trait="live-test",
        population=population, summary_stats_ref=summary_ref, ld_matrix_ref=ld_ref,
    ))
    assert fine.storage_ref and fine.provenance.tool_version

    coloc_result = backend.coloc(ColocRequest(
        interval=interval, organism="Homo sapiens", assembly="GRCh38", trait="live-test",
        tissues=[os.getenv("CELLXP_GWAS_TEST_TISSUE", "whole_blood")],
        gwas_stats_ref=os.environ["CELLXP_GWAS_TEST_GWAS_STATS_REF"],
        qtl_stats_ref=os.environ["CELLXP_GWAS_TEST_QTL_STATS_REF"],
    ))
    assert coloc_result.storage_ref and coloc_result.provenance.tool_version
