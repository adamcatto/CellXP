"""Network-free worker transport tests for AGS-2/5."""

from __future__ import annotations

import httpx
import pytest
from cellxp.domain.enums import ConfidenceBand
from cellxp.domain.models import GenomicInterval, Variant
from cellxp.services.alphagenome import (
    AlphaGenomeService,
    HttpModelBackend,
    RoutedHttpModelBackend,
    SequenceScoringRequest,
    SpliceEffectRequest,
    TrackPredictionRequest,
    VariantEffectRequest,
)
from cellxp.services.base import ServiceOutcome
from pydantic import ValidationError


def _client(handler) -> httpx.Client:
    return httpx.Client(base_url="https://worker.test", transport=httpx.MockTransport(handler))


def _variant() -> Variant:
    return Variant(chrom="chr1", pos=100, ref="A", alt="T", assembly="GRCh38")


def test_variant_request_uses_versioned_endpoint_and_validates_response() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert request.url.path == "/v1/score-variants"
        assert b'"organism":"Homo sapiens"' in request.content
        return httpx.Response(200, json={"per_variant": [{
            "variant_id": "chr1:101:A>T",
            "deltas": [{"assay": "DNASE", "value": -0.4, "direction": "down"}],
            "top_effects": [],
            "confidence": {"band": "medium", "score": 0.7},
        }]})

    backend = HttpModelBackend(
        "https://ignored.test", client=_client(handler), version="alphagenome-2026-01"
    )
    result = AlphaGenomeService(model_backend=backend).score_variants(VariantEffectRequest(
        variants=[_variant()], organism="Homo sapiens", assembly="GRCh38",
    ))

    assert result.outcome is ServiceOutcome.OK
    assert result.value is not None
    assert result.value.per_variant[0].confidence.score == 0.7
    assert result.steps[0].tool_version == "alphagenome-2026-01"
    assert result.evidence[0].provenance.tool_version == "alphagenome-2026-01"
    assert result.evidence[0].provenance.input_hash is not None
    assert result.evidence[0].provenance.output_hash is not None


@pytest.mark.parametrize(
    ("path", "call"),
    [
        ("/v1/score-sequences", lambda backend: backend.score_sequences(SequenceScoringRequest(
            sequences=["ACGT"], organism="Escherichia coli",
        ))),
        ("/v1/predict-tracks", lambda backend: backend.predict_tracks(TrackPredictionRequest(
            interval=GenomicInterval(chrom="chr1", start=0, end=4, assembly="GRCh38"),
            organism="Homo sapiens", assembly="GRCh38",
        ))),
        ("/v1/score-splicing", lambda backend: backend.score_splicing(SpliceEffectRequest(
            variant=_variant(), organism="Homo sapiens", assembly="GRCh38",
        ))),
    ],
)
def test_other_operations_use_stable_paths(path: str, call) -> None:
    payloads = {
        "/v1/score-sequences": {"scores": [0.2], "model": "evo2"},
        "/v1/predict-tracks": {"tracks": {"DNASE": [0.1]}, "model": "alphagenome"},
        "/v1/score-splicing": {
            "donor_loss": 0.1, "confidence": {"band": ConfidenceBand.LOW.value}
        },
    }

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == path
        return httpx.Response(200, json=payloads[path])

    call(HttpModelBackend("https://ignored.test", client=_client(handler)))


def test_bad_worker_payload_is_recoverable_service_failure() -> None:
    backend = HttpModelBackend(
        "https://ignored.test",
        client=_client(lambda request: httpx.Response(200, json={"per_variant": [{}]})),
    )
    result = AlphaGenomeService(model_backend=backend).score_variants(VariantEffectRequest(
        variants=[_variant()], organism="Homo sapiens", assembly="GRCh38",
    ))
    assert result.outcome is ServiceOutcome.FAILURE
    assert result.error is not None and result.error.kind == "BackendError"


def test_sequence_evidence_hashes_input_without_exposing_sequence() -> None:
    backend = HttpModelBackend(
        "https://ignored.test",
        client=_client(lambda request: httpx.Response(200, json={
            "scores": [0.2], "model": "evo2",
        })),
        version="evo2-rev",
    )
    result = AlphaGenomeService(model_backend=backend).score_sequences(SequenceScoringRequest(
        sequences=["ACGT"], organism="Escherichia coli",
    ))
    assert result.outcome is ServiceOutcome.OK
    provenance = result.evidence[0].provenance
    assert "sequences" not in provenance.inputs
    assert len(provenance.inputs["sequence_hashes"][0]) == 64
    assert provenance.tool_version == "evo2-rev"


def test_direct_backend_surfaces_contract_validation_error() -> None:
    backend = HttpModelBackend(
        "https://ignored.test",
        client=_client(lambda request: httpx.Response(200, json={"scores": "invalid"})),
    )
    with pytest.raises(ValidationError):
        backend.score_sequences(SequenceScoringRequest(
            sequences=["ACGT"], organism="Escherichia coli"
        ))


def test_from_environment_is_none_when_endpoint_is_unset(monkeypatch) -> None:
    monkeypatch.delenv("ALPHAGENOME_SERVICE_URL", raising=False)
    assert HttpModelBackend.from_environment() is None


def test_from_environment_records_revision(monkeypatch) -> None:
    monkeypatch.setenv("ALPHAGENOME_SERVICE_URL", "https://worker.test")
    monkeypatch.setenv("ALPHAGENOME_MODEL_REVISION", "evo2-rev-42")
    backend = HttpModelBackend.from_environment()
    assert backend is not None
    assert backend.version == "evo2-rev-42"
    backend.close()


def test_routed_backend_dispatches_by_organism() -> None:
    observed: list[str] = []

    def alpha_handler(request: httpx.Request) -> httpx.Response:
        observed.append("alpha")
        return httpx.Response(200, json={"per_variant": []})

    def evo_handler(request: httpx.Request) -> httpx.Response:
        observed.append("evo")
        return httpx.Response(200, json={"per_variant": []})

    backend = RoutedHttpModelBackend(
        HttpModelBackend("https://alpha.test", client=_client(alpha_handler)),
        HttpModelBackend("https://evo.test", client=_client(evo_handler)),
    )
    backend.score_variants(VariantEffectRequest(
        variants=[_variant()], organism="Homo sapiens", assembly="GRCh38"
    ))
    backend.score_variants(VariantEffectRequest(
        variants=[Variant(chrom="NC_000913.3", pos=10, ref="A", alt="G",
                          assembly="GCF_000005845.2")],
        organism="Escherichia coli", assembly="GCF_000005845.2",
    ))
    assert observed == ["alpha", "evo"]
