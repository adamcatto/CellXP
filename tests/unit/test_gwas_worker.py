"""Deterministic contract coverage for the deployable X1 statistical worker."""

from __future__ import annotations

import json

from cellxp.domain.evidence import Provenance
from cellxp.domain.models import GenomicInterval
from cellxp.services.gwas import (
    ColocBatchResult,
    ColocRequest,
    ColocResult,
    CredibleSet,
    CredibleVariant,
    FineMapRequest,
    FineMapResult,
    LdPair,
    LdRequest,
    LdResult,
)
from cellxp.services.gwas.worker_backend import GwasWorkerBackend
from cellxp.storage.object_store import FilesystemObjectStore
from fastapi.testclient import TestClient


def interval() -> GenomicInterval:
    return GenomicInterval(assembly="GRCh38", chrom="chr1", start=100, end=200)


class Engine:
    revision = "fixture-pinned-1"

    def compute_ld(self, request: LdRequest) -> LdResult:
        return LdResult(
            pairs=[LdPair(variant_a="rs1", variant_b="rs2", r2=0.8)],
            population=request.population, panel="fixture-panel",
            assumptions=["fixture"], provenance=Provenance(tool="PLINK2", tool_version="fixture"),
        )

    def fine_map(self, request: FineMapRequest) -> FineMapResult:
        return FineMapResult(
            credible_sets=[CredibleSet(
                id="cs1", variants=[CredibleVariant(variant_id="rs1", pip=0.9)],
                region=request.interval, coverage=0.95,
            )], assumptions=["fixture"], input_datasets=[request.summary_stats_ref],
            provenance=Provenance(tool="susieR", tool_version="fixture"),
        )

    def coloc(self, request: ColocRequest) -> ColocBatchResult:
        return ColocBatchResult(
            results=[ColocResult(
                trait=request.trait, tissue=request.tissues[0], h4=0.91,
                gwas_dataset=request.gwas_stats_ref, qtl_dataset=request.qtl_stats_ref,
            )], assumptions=["fixture"],
            input_datasets=[request.gwas_stats_ref, request.qtl_stats_ref],
            provenance=Provenance(tool="coloc", tool_version="fixture"),
        )


def backend(tmp_path) -> GwasWorkerBackend:
    return GwasWorkerBackend(Engine(), FilesystemObjectStore(tmp_path))


def test_worker_backend_persists_ld_finemap_and_coloc(tmp_path) -> None:
    worker = backend(tmp_path)
    results = [
        worker.compute_ld(LdRequest(interval=interval(), organism="Homo sapiens",
                                    assembly="GRCh38", population="EUR")),
        worker.fine_map(FineMapRequest(interval=interval(), organism="Homo sapiens",
                                       assembly="GRCh38", trait="LDL",
                                       summary_stats_ref="stats", ld_matrix_ref="ld")),
        worker.coloc(ColocRequest(interval=interval(), organism="Homo sapiens",
                                  assembly="GRCh38", trait="LDL", tissues=["liver"],
                                  gwas_stats_ref="gwas", qtl_stats_ref="qtl")),
    ]
    for result in results:
        assert result.storage_ref
        payload = json.loads(worker.store.get(result.storage_ref))
        assert payload
        assert result.provenance.output_hash


def test_worker_http_endpoints_validate_and_persist(monkeypatch, tmp_path) -> None:
    from cellxp.services.gwas import worker as module
    monkeypatch.setattr(module, "get_backend", lambda: backend(tmp_path))
    client = TestClient(module.app)
    response = client.post("/v1/ld", json={
        "interval": interval().model_dump(mode="json"), "organism": "Homo sapiens",
        "assembly": "GRCh38", "population": "EUR",
    })
    assert response.status_code == 200
    assert response.json()["storage_ref"].startswith("cas/")


def test_external_engine_fails_closed_without_ld_matrix(tmp_path) -> None:
    from cellxp.services.gwas.worker_backend import ExternalStatisticalEngine, GwasWorkerConfig
    engine = ExternalStatisticalEngine(FilesystemObjectStore(tmp_path), GwasWorkerConfig())
    request = FineMapRequest(interval=interval(), organism="Homo sapiens", assembly="GRCh38",
                             trait="LDL", summary_stats_ref="stats")
    import pytest
    with pytest.raises(ValueError, match="ld_matrix_ref"):
        engine.fine_map(request)
