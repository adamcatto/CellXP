"""Deterministic contract fixtures for isolated AlphaGenome and Evo 2 workers."""

from __future__ import annotations

from fastapi.testclient import TestClient

from cellxp.services.alphagenome.alphagenome_worker import app as alphagenome_app
from cellxp.services.alphagenome.evo_worker import app as evo_app


def test_worker_health_and_version_are_manifest_backed(monkeypatch) -> None:
    monkeypatch.setenv("CELLXP_SEQUENCE_WORKER_MODE", "fixture")
    for app, expected_model in ((alphagenome_app, "alphagenome"), (evo_app, "evo2")):
        client = TestClient(app)
        health = client.get("/health").json()
        version = client.get("/version").json()
        assert health["status"] == "ok"
        assert health["model"] == expected_model
        assert len(health["manifest_sha256"]) == 64
        assert version["model_revision"] == health["model_revision"]


def test_alphagenome_rejects_microbe_before_fixture_inference(monkeypatch) -> None:
    monkeypatch.setenv("CELLXP_SEQUENCE_WORKER_MODE", "fixture")
    response = TestClient(alphagenome_app).post("/v1/score-variants", json={
        "variants": [{"chrom": "NC_000913.3", "pos": 10, "ref": "A", "alt": "G",
                      "assembly": "GCF_000005845.2"}],
        "organism": "Escherichia coli",
        "assembly": "GCF_000005845.2",
    })
    assert response.status_code == 422
    assert "mammalian" in response.json()["detail"]


def test_evo_fixture_is_deterministic_and_accepts_microbe(monkeypatch) -> None:
    monkeypatch.setenv("CELLXP_SEQUENCE_WORKER_MODE", "fixture")
    client = TestClient(evo_app)
    payload = {
        "sequences": ["ACGTACGT"],
        "organism": "Escherichia coli",
        "assembly": "GCF_000005845.2",
        "scoring_type": "embedding",
    }
    first = client.post("/v1/score-sequences", json=payload)
    second = client.post("/v1/score-sequences", json=payload)
    assert first.status_code == 200
    assert first.json() == second.json()
    assert first.json()["model"].startswith("evo2@")


def test_workers_fail_closed_without_runtime(monkeypatch) -> None:
    monkeypatch.setenv("CELLXP_SEQUENCE_WORKER_MODE", "production")
    response = TestClient(evo_app).post("/v1/score-sequences", json={
        "sequences": ["ACGT"], "organism": "Homo sapiens", "assembly": "GRCh38"
    })
    assert response.status_code == 503
    assert TestClient(evo_app).get("/health").json()["status"] == "not_ready"


def test_evo_rejects_invalid_alphabet(monkeypatch) -> None:
    monkeypatch.setenv("CELLXP_SEQUENCE_WORKER_MODE", "fixture")
    response = TestClient(evo_app).post("/v1/score-sequences", json={
        "sequences": ["ACGTX"], "organism": "Homo sapiens", "assembly": "GRCh38"
    })
    assert response.status_code == 422
