"""Deterministic contract tests for CRISPR scoring/off-target worker adapters."""

from __future__ import annotations

import httpx
import pytest

from cellxp.services.crispr import (
    DeterministicCrisprBackend, GuideScoringRequest, HttpCrisprBackend, OffTargetRequest,
)


def test_http_worker_retries_and_validates_off_target_result() -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        assert request.url.path == "/v1/off-targets"
        if calls == 1:
            return httpx.Response(429)
        return httpx.Response(200, json={"hits": {"ACGTACGTACGTACGTACGT": []}})

    backend = HttpCrisprBackend("https://worker.test", retries=1,
                                client=httpx.Client(base_url="https://worker.test",
                                                    transport=httpx.MockTransport(handler)))
    result = backend.enumerate_off_targets(OffTargetRequest(
        guides=["ACGTACGTACGTACGTACGT"], organism="Homo sapiens", assembly="GRCh38",
    ))
    assert result.hits["ACGTACGTACGTACGTACGT"] == []
    assert calls == 2


def test_deterministic_scoring_is_stable_and_rejects_ambiguous_dna() -> None:
    backend = DeterministicCrisprBackend()
    request = GuideScoringRequest(guides=["ACGTACGTACGTACGTACGT"],
                                  organism="Homo sapiens", assembly="GRCh38")
    assert backend.score_on_target(request) == backend.score_on_target(request)
    with pytest.raises(ValueError, match="unambiguous DNA"):
        backend.score_on_target(request.model_copy(update={"guides": ["NNNNNNNNNNNNNNNNNNNN"]}))


def test_environment_selection_requires_url(monkeypatch) -> None:  # noqa: ANN001
    from cellxp.services.crispr.backends import crispr_backend_from_environment

    monkeypatch.setenv("CRISPR_BACKEND", "http")
    monkeypatch.delenv("CRISPR_SERVICE_URL", raising=False)
    with pytest.raises(ValueError, match="CRISPR_SERVICE_URL"):
        crispr_backend_from_environment()
