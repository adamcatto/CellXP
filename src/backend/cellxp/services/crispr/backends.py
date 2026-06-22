"""CRISPR worker and offline scoring adapters (FR-15, CRS-1..5)."""

from __future__ import annotations

import hashlib
import os
import time
from typing import Any, TypeVar

import httpx
from pydantic import BaseModel

from .schemas import (
    CrisprRequest, CrisprResult, EditOutcomeRequest, EditOutcomeResult, GuideScoringRequest,
    GuideScoringResult, OffTargetRequest, OffTargetResult,
)

T = TypeVar("T", bound=BaseModel)
_RETRYABLE = {429, 500, 502, 503, 504}


class HttpCrisprBackend:
    """Typed client for pinned Rule Set 2/CFD/Cas-OFFinder workers."""

    name = "crispr_http"

    def __init__(self, base_url: str, *, token: str | None = None, timeout: float = 120.0,
                 retries: int = 2, version: str = "remote", client: httpx.Client | None = None):
        if not base_url.strip():
            raise ValueError("CRISPR service base URL must not be empty")
        self.version, self.retries = version, retries
        headers = {"Accept": "application/json"}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        self._client = client or httpx.Client(base_url=base_url.rstrip("/"), timeout=timeout,
                                               headers=headers)

    def design_guides(self, request: CrisprRequest) -> CrisprResult:
        return self._post("/v1/design-guides", request, CrisprResult)

    def enumerate_off_targets(self, request: OffTargetRequest) -> OffTargetResult:
        return self._post("/v1/off-targets", request, OffTargetResult)

    def score_on_target(self, request: GuideScoringRequest) -> GuideScoringResult:
        return self._post("/v1/on-target-scores", request, GuideScoringResult)

    def predict_edit_outcomes(self, request: EditOutcomeRequest) -> EditOutcomeResult:
        return self._post("/v1/edit-outcomes", request, EditOutcomeResult)

    def attest(self) -> dict[str, Any]:
        response = self._client.get("/health")
        response.raise_for_status()
        return dict(response.json())

    def _post(self, path: str, request: BaseModel, result: type[T]) -> T:
        response = _request_with_retries(self._client, path, self.retries,
                                         json=request.model_dump(mode="json"))
        return result.model_validate(response.json())


class DeterministicCrisprBackend:
    """Offline scoring fallback for development; does not claim genome-wide search.

    Scores are stable sequence-QC heuristics, not Rule Set 2 or CFD predictions. Guide design and
    edit outcomes return empty results so callers cannot mistake fabricated candidates for evidence.
    """

    name = "deterministic_sequence_qc"
    version = "1"

    def design_guides(self, request: CrisprRequest) -> CrisprResult:
        return CrisprResult(guides=[], editing_system=request.cas or "unconfigured",
                            rationale="offline fallback cannot retrieve target sequence")

    def enumerate_off_targets(self, request: OffTargetRequest) -> OffTargetResult:
        return OffTargetResult(hits={guide: [] for guide in request.guides})

    def score_on_target(self, request: GuideScoringRequest) -> GuideScoringResult:
        scores = {}
        for raw in request.guides:
            guide = _validated_dna(raw)
            gc = (guide.count("G") + guide.count("C")) / len(guide)
            # Prefer 40-60% GC and penalize homopolymers; stable QC only.
            gc_score = max(0.0, 1.0 - abs(gc - 0.5) * 3.0)
            homopolymer_penalty = 0.25 if any(base * 4 in guide for base in "ACGT") else 0.0
            digest_tiebreak = int(hashlib.sha256(guide.encode()).hexdigest()[:4], 16) / 65535e4
            scores[raw] = round(max(0.0, min(1.0, gc_score - homopolymer_penalty + digest_tiebreak)), 6)
        return GuideScoringResult(scores=scores)

    def predict_edit_outcomes(self, request: EditOutcomeRequest) -> EditOutcomeResult:
        return EditOutcomeResult(efficiencies={}, outcome_model="unavailable-offline")


def crispr_backend_from_environment():  # noqa: ANN201
    mode = os.getenv("CRISPR_BACKEND", "none").strip().lower()
    if mode == "none":
        return None
    if mode == "deterministic":
        return DeterministicCrisprBackend()
    if mode == "http":
        url = os.getenv("CRISPR_SERVICE_URL", "").strip()
        if not url:
            raise ValueError("CRISPR_BACKEND=http requires CRISPR_SERVICE_URL")
        return HttpCrisprBackend(
            url, token=os.getenv("CRISPR_SERVICE_TOKEN") or None,
            timeout=float(os.getenv("CRISPR_SERVICE_TIMEOUT_SECONDS", "120")),
            retries=int(os.getenv("CRISPR_SERVICE_RETRIES", "2")),
            version=os.getenv("CRISPR_TOOL_REVISION", "remote"),
        )
    raise ValueError(f"unknown CRISPR_BACKEND {mode!r}")


def _request_with_retries(client: httpx.Client, path: str, retries: int,
                          **kwargs: Any) -> httpx.Response:
    for attempt in range(retries + 1):
        try:
            response = client.post(path, **kwargs)
            if response.status_code not in _RETRYABLE or attempt == retries:
                response.raise_for_status()
                return response
        except httpx.TransportError:
            if attempt == retries:
                raise
        time.sleep(0.05 * (2 ** attempt))
    raise AssertionError("retry loop exhausted")


def _validated_dna(value: str) -> str:
    sequence = value.strip().upper()
    if not 15 <= len(sequence) <= 30 or set(sequence) - set("ACGT"):
        raise ValueError("guide must contain 15-30 unambiguous DNA bases")
    return sequence
