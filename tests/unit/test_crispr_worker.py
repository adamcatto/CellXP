"""Contract and attestation tests for the isolated CRISPR worker."""

from __future__ import annotations

import hashlib
import json
import sys
import types

import httpx
from fastapi.testclient import TestClient

from cellxp.services.crispr.backends import HttpCrisprBackend
from cellxp.services.crispr.worker import app
from cellxp.services.crispr.runtime import parse_cas_offinder_line
from cellxp.services.crispr.worker_contract import (
    index_manifest,
    packaged_worker_manifest,
    production_backend,
)


def _fixture_client(monkeypatch) -> TestClient:  # noqa: ANN001
    monkeypatch.setenv("CELLXP_CRISPR_WORKER_MODE", "contract_fixture")
    index_manifest.cache_clear()
    production_backend.cache_clear()
    return TestClient(app)


def test_fixture_health_attests_mode_and_circular_microbe(monkeypatch) -> None:  # noqa: ANN001
    health = _fixture_client(monkeypatch).get("/health")
    assert health.status_code == 200
    body = health.json()
    assert body["mode"] == "contract_fixture"
    assert body["algorithms"] == ["sequence_qc_contract_fixture"]
    assert set(body["assemblies"]) == {"GRCh38", "GCF_000005845.2"}
    assert len(body["source_manifest_sha256"]) == 64


def test_fixture_never_accepts_rule_set_2_label(monkeypatch) -> None:  # noqa: ANN001
    client = _fixture_client(monkeypatch)
    payload = {
        "guides": ["GAGTCCGAGCAGAAGAAGAA"],
        "organism": "Homo sapiens",
        "assembly": "GRCh38",
        "model": "rule_set_2",
    }
    response = client.post("/v1/on-target-scores", json=payload)
    assert response.status_code == 422
    assert "cannot claim Rule Set 2" in response.json()["detail"]
    payload["model"] = "contract_fixture_qc"
    accepted = client.post("/v1/on-target-scores", json=payload)
    assert accepted.status_code == 200


def test_fixture_microbe_request_uses_attested_circular_assembly(monkeypatch) -> None:  # noqa: ANN001
    response = _fixture_client(monkeypatch).post("/v1/design-guides", json={
        "target": "lacZ",
        "organism": "Escherichia coli",
        "assembly": "GCF_000005845.2",
        "edit_type": "knockout",
    })
    assert response.status_code == 200
    assert response.json()["guides"] == []
    assert "topology=circular" in response.json()["rationale"]


def test_unknown_assembly_is_rejected_before_scoring(monkeypatch) -> None:  # noqa: ANN001
    response = _fixture_client(monkeypatch).post("/v1/on-target-scores", json={
        "guides": ["GAGTCCGAGCAGAAGAAGAA"],
        "organism": "Homo sapiens",
        "assembly": "hg19",
    })
    assert response.status_code == 422
    assert "no attested off-target index" in response.json()["detail"]


def test_production_rejects_index_checksum_mismatch(monkeypatch, tmp_path) -> None:  # noqa: ANN001
    index_file = tmp_path / "grch38.index"
    index_file.write_bytes(b"actual index")
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps({
        "schema_version": "1.0",
        "indexes": [{
            "organism": "Homo sapiens", "assembly": "GRCh38", "topology": "linear",
            "files": [{"path": index_file.name, "sha256": "0" * 64}],
        }],
    }))
    monkeypatch.setenv("CELLXP_CRISPR_WORKER_MODE", "production")
    monkeypatch.setenv("CRISPR_INDEX_MANIFEST", str(manifest_path))
    index_manifest.cache_clear()
    response = TestClient(app).get("/health")
    assert response.status_code == 503
    assert "checksum mismatch" in response.json()["detail"]


def test_production_runtime_must_attest_exact_source_revisions(monkeypatch, tmp_path) -> None:  # noqa: ANN001
    index_file = tmp_path / "index.bin"
    index_file.write_bytes(b"index")
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps({
        "schema_version": "1.0",
        "indexes": [{
            "organism": "Homo sapiens", "assembly": "GRCh38", "topology": "linear",
            "files": [{
                "path": index_file.name,
                "sha256": hashlib.sha256(index_file.read_bytes()).hexdigest(),
            }],
        }],
    }))

    class Runtime:
        def attest(self):  # noqa: ANN201
            return {"source_revisions": {"cas-offinder": "wrong"}}

    module = types.ModuleType("test_crispr_runtime")
    module.factory = lambda source, indexes: Runtime()  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, module.__name__, module)
    monkeypatch.setenv("CELLXP_CRISPR_WORKER_MODE", "production")
    monkeypatch.setenv("CRISPR_INDEX_MANIFEST", str(manifest_path))
    monkeypatch.setenv("CELLXP_CRISPR_RUNTIME_FACTORY", "test_crispr_runtime:factory")
    index_manifest.cache_clear()
    production_backend.cache_clear()
    response = TestClient(app).get("/health")
    assert response.status_code == 503
    assert "source revisions do not attest" in response.json()["detail"]


def test_http_backend_reads_worker_attestation() -> None:
    manifest = packaged_worker_manifest()
    revisions = {source.name: source.revision for source in manifest.sources}

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/health"
        return httpx.Response(200, json={"status": "ok", "source_revisions": revisions})

    backend = HttpCrisprBackend(
        "https://worker.test",
        client=httpx.Client(base_url="https://worker.test", transport=httpx.MockTransport(handler)),
    )
    assert backend.attest()["source_revisions"] == revisions


def test_cas_offinder_bulge_output_parser_retains_guide_id() -> None:
    parsed = parse_cas_offinder_line(
        "guide-3\tDNA\tGAGTCCGAGCAGAAGAAGAANNN\tGAGTCCGAGCAGAAGAAGAATGG\t"
        "chr1\t12345\t-\t2\t0"
    )
    assert parsed == (
        "guide-3", "GAGTCCGAGCAGAAGAAGAANNN", "GAGTCCGAGCAGAAGAAGAATGG",
        "chr1", "12345", "-", "2",
    )


def test_cas_offinder_v24_output_parser_reads_trailing_id() -> None:
    parsed = parse_cas_offinder_line(
        "GAGTCCGAGCAGAAGAAGAANNN\tchr1\t12345\tGAGTCCGAGCAGAAGAAGAATGG\t+\t1\tguide-0"
    )
    assert parsed[0] == "guide-0"
    assert parsed[3:] == ("chr1", "12345", "+", "1")
