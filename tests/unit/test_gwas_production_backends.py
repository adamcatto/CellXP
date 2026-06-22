"""Deterministic contract tests for GWAS Catalog/QTL and worker adapters."""

from __future__ import annotations

import httpx

from cellxp.domain.models import Variant
from cellxp.services.gwas import EbiGwasQtlBackend, GwasRequest, HttpGwasBackend


def _request() -> GwasRequest:
    return GwasRequest(subject=Variant(chrom="1", pos=100, ref="A", alt="G", assembly="GRCh38",
                                       rsid="rs123"), organism="Homo sapiens", assembly="GRCh38")


def test_ebi_adapter_normalizes_gwas_and_qtl_records() -> None:
    def gwas_handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["rs_id"] == "rs123"
        return httpx.Response(200, json={"_embedded": {"associations": [{
            "pvalue": 1e-9, "beta": 0.2, "riskAllele": "G",
            "study": {"accessionId": "GCST1"},
            "diseaseTrait": {"trait": "LDL cholesterol"}, "pubmedId": "12345",
        }]}})

    def eqtl_handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["rsid"] == "rs123"
        return httpx.Response(200, json={"items": [{
            "p_value": 2e-6, "beta": -0.1, "gene_id": "ENSG1",
            "dataset_id": "QTD1", "tissue": "liver", "alt": "G",
        }]})

    backend = EbiGwasQtlBackend(
        gwas_client=httpx.Client(base_url="https://gwas.test",
                                 transport=httpx.MockTransport(gwas_handler)),
        eqtl_client=httpx.Client(base_url="https://eqtl.test",
                                transport=httpx.MockTransport(eqtl_handler)),
    )
    result = backend.lookup_associations(_request())
    assert [item.source for item in result.associations] == [
        "NHGRI-EBI GWAS Catalog", "eQTL Catalogue",
    ]
    assert result.provenance.tool_version == "gwas-rest-v2+eqtl-v3"


def test_http_worker_retries_transient_status_and_validates_result() -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls == 1:
            return httpx.Response(503)
        return httpx.Response(200, json={
            "associations": [],
            "confidence": {"band": "unknown"},
            "coverage_note": "none",
        })

    backend = HttpGwasBackend("https://worker.test", retries=1,
                              client=httpx.Client(base_url="https://worker.test",
                                                  transport=httpx.MockTransport(handler)))
    assert backend.lookup_associations(_request()).coverage_note == "none"
    assert calls == 2


def test_environment_selection_is_opt_in(monkeypatch) -> None:  # noqa: ANN001
    from cellxp.services.gwas.backends import gwas_backend_from_environment

    monkeypatch.delenv("GWAS_BACKEND", raising=False)
    assert gwas_backend_from_environment() is None
    monkeypatch.setenv("GWAS_BACKEND", "deterministic")
    assert gwas_backend_from_environment().name == "deterministic_empty"
