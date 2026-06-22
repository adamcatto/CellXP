"""Opt-in live service checks; excluded unless explicitly enabled by environment."""

from __future__ import annotations

import os

import pytest

from cellxp.domain.models import Variant
from cellxp.services.crispr import GuideScoringRequest, crispr_backend_from_environment
from cellxp.services.gwas import GwasRequest, gwas_backend_from_environment

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
