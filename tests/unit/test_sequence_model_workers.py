"""Deterministic contract fixtures for isolated AlphaGenome and Evo 2 workers."""

from __future__ import annotations

from cellxp.services.alphagenome.alphagenome_worker import app as alphagenome_app
from cellxp.services.alphagenome.evo_worker import app as evo_app
from cellxp.services.alphagenome.sdk_backends import AlphaGenomeSdkBackend, Evo2SdkBackend
from fastapi.testclient import TestClient


class _Genome:
    @staticmethod
    def Interval(chromosome, start, end, strand="."):
        return {"chromosome": chromosome, "start": start, "end": end, "strand": strand}

    @staticmethod
    def Variant(**kwargs):
        return kwargs


class _DnaClient:
    class Organism:
        HOMO_SAPIENS = "human"
        MUS_MUSCULUS = "mouse"


class _Table:
    def to_dict(self, orient):
        assert orient == "records"
        return [
            {"output_type": "RNA_SEQ", "biosample_name": "liver", "raw_score": 0.75},
            {"output_type": "ATAC", "biosample_name": "heart", "raw_score": -0.25},
        ]


class _VariantScorers:
    @staticmethod
    def tidy_scores(scores):
        assert scores == ["score"]
        return _Table()


class _AlphaClient:
    def __init__(self):
        self.calls = []

    def score_variant(self, **kwargs):
        self.calls.append(kwargs)
        return ["score"]


class _EvoModel:
    def score_sequences(self, sequences, **kwargs):
        assert kwargs == {
            "batch_size": 1, "reduce_method": "mean", "average_reverse_complement": True,
        }
        return [-1.25 for _ in sequences]


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


def test_packaged_alphagenome_adapter_maps_official_score_variant_contract(monkeypatch) -> None:
    monkeypatch.setenv("CELLXP_SEQUENCE_WORKER_MODE", "production")
    client = _AlphaClient()
    backend = AlphaGenomeSdkBackend(
        client, genome=_Genome, dna_client=_DnaClient, variant_scorers=_VariantScorers
    )
    monkeypatch.setattr(
        "cellxp.services.alphagenome.worker_common.production_backend",
        lambda model: backend,
    )
    response = TestClient(alphagenome_app).post("/v1/score-variants", json={
        "variants": [{"chrom": "1", "pos": 99, "ref": "A", "alt": "G", "assembly": "GRCh38"}],
        "organism": "Homo sapiens", "assembly": "GRCh38",
        "assays": ["RNA_SEQ"], "tissues": ["liver"],
    })
    assert response.status_code == 200
    effect = response.json()["per_variant"][0]
    assert effect["variant_id"] == "1:100:A>G"
    assert effect["deltas"] == [
        {"assay": "RNA_SEQ", "tissue": "liver", "value": 0.75, "direction": "up"}
    ]
    call = client.calls[0]
    assert call["variant"]["position"] == 100
    assert call["interval"]["end"] - call["interval"]["start"] == 131_072


def test_packaged_evo_adapter_calls_official_sequence_scoring_contract(monkeypatch) -> None:
    monkeypatch.setenv("CELLXP_SEQUENCE_WORKER_MODE", "production")
    backend = Evo2SdkBackend(_EvoModel())
    monkeypatch.setattr(
        "cellxp.services.alphagenome.worker_common.production_backend", lambda model: backend
    )
    response = TestClient(evo_app).post("/v1/score-sequences", json={
        "sequences": ["acgt"], "organism": "Escherichia coli",
        "assembly": "GCF_000005845.2", "scoring_type": "likelihood",
    })
    assert response.status_code == 200
    assert response.json()["scores"] == [-1.25]
    assert response.json()["model"] == "evo2==0.6.0:evo2_7b"


def test_evo_coordinate_only_variant_requests_fail_closed(monkeypatch) -> None:
    monkeypatch.setenv("CELLXP_SEQUENCE_WORKER_MODE", "production")
    monkeypatch.setattr(
        "cellxp.services.alphagenome.worker_common.production_backend",
        lambda model: Evo2SdkBackend(_EvoModel()),
    )
    response = TestClient(evo_app).post("/v1/score-variants", json={
        "variants": [{"chrom": "NC_000913.3", "pos": 10, "ref": "A", "alt": "G"}],
        "organism": "Escherichia coli", "assembly": "GCF_000005845.2",
    })
    assert response.status_code == 422
    assert "sequence contexts" in response.json()["detail"]
