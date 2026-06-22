"""HTTP transport for independently deployed AlphaGenome/Evo 2 model workers."""

from __future__ import annotations

import os
from typing import TypeVar

import httpx
from pydantic import BaseModel

from .schemas import (
    SequenceScoringRequest,
    SequenceScoringResult,
    SpliceEffectRequest,
    SpliceEffectResult,
    TrackPredictionRequest,
    TrackPredictionResult,
    VariantEffectRequest,
    VariantEffectResult,
    select_oracle,
)

T = TypeVar("T", bound=BaseModel)


class HttpModelBackend:
    """Typed client for the stable sequence-model worker API.

    Worker endpoints accept the corresponding request schema as JSON and return the
    result schema directly. Authentication is optional and sent as a bearer token.
    """

    name = "sequence_model_http"

    def __init__(
        self,
        base_url: str,
        *,
        token: str | None = None,
        timeout: float = 120.0,
        version: str = "remote",
        client: httpx.Client | None = None,
    ) -> None:
        if not base_url.strip():
            raise ValueError("model service base URL must not be empty")
        self.version = version
        self._owns_client = client is None
        headers = {"Accept": "application/json"}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        self._client = client or httpx.Client(
            base_url=base_url.rstrip("/"), timeout=timeout, headers=headers
        )

    @classmethod
    def from_environment(cls) -> HttpModelBackend | None:
        """Build from deployment configuration, or return None when unconfigured."""
        url = os.getenv("ALPHAGENOME_SERVICE_URL", "").strip()
        if not url:
            return None
        timeout = float(os.getenv("ALPHAGENOME_SERVICE_TIMEOUT_SECONDS", "120"))
        return cls(
            url,
            token=os.getenv("ALPHAGENOME_SERVICE_TOKEN") or None,
            timeout=timeout,
            version=os.getenv("ALPHAGENOME_MODEL_REVISION", "remote"),
        )

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def score_variants(self, request: VariantEffectRequest) -> VariantEffectResult:
        return self._post("/v1/score-variants", request, VariantEffectResult)

    def score_sequences(self, request: SequenceScoringRequest) -> SequenceScoringResult:
        return self._post("/v1/score-sequences", request, SequenceScoringResult)

    def predict_tracks(self, request: TrackPredictionRequest) -> TrackPredictionResult:
        return self._post("/v1/predict-tracks", request, TrackPredictionResult)

    def score_splicing(self, request: SpliceEffectRequest) -> SpliceEffectResult:
        return self._post("/v1/score-splicing", request, SpliceEffectResult)

    def _post(self, path: str, request: BaseModel, result_type: type[T]) -> T:
        response = self._client.post(path, json=request.model_dump(mode="json"))
        response.raise_for_status()
        return result_type.model_validate(response.json())


class RoutedHttpModelBackend:
    """Route the stable model contract to separately deployed AlphaGenome and Evo workers."""

    name = "sequence_model_http_router"

    def __init__(self, alphagenome: HttpModelBackend, evo2: HttpModelBackend) -> None:
        self.alphagenome = alphagenome
        self.evo2 = evo2
        self.version = f"alphagenome={alphagenome.version};evo2={evo2.version}"

    @classmethod
    def from_environment(cls) -> RoutedHttpModelBackend | None:
        alpha_url = os.getenv("ALPHAGENOME_SERVICE_URL", "").strip()
        evo_url = os.getenv("EVO2_SERVICE_URL", "").strip()
        if not alpha_url or not evo_url:
            return None
        timeout = float(os.getenv("SEQUENCE_MODEL_SERVICE_TIMEOUT_SECONDS", "120"))
        return cls(
            HttpModelBackend(
                alpha_url,
                token=os.getenv("ALPHAGENOME_SERVICE_TOKEN") or None,
                timeout=timeout,
                version=os.getenv("ALPHAGENOME_MODEL_REVISION", "remote"),
            ),
            HttpModelBackend(
                evo_url,
                token=os.getenv("EVO2_SERVICE_TOKEN") or None,
                timeout=timeout,
                version=os.getenv("EVO2_MODEL_REVISION", "remote"),
            ),
        )

    def close(self) -> None:
        self.alphagenome.close()
        self.evo2.close()

    def score_variants(self, request: VariantEffectRequest) -> VariantEffectResult:
        return self._for_organism(request.organism).score_variants(request)

    def score_sequences(self, request: SequenceScoringRequest) -> SequenceScoringResult:
        return self.evo2.score_sequences(request)

    def predict_tracks(self, request: TrackPredictionRequest) -> TrackPredictionResult:
        return self._for_organism(request.organism).predict_tracks(request)

    def score_splicing(self, request: SpliceEffectRequest) -> SpliceEffectResult:
        return self.alphagenome.score_splicing(request)

    def _for_organism(self, organism: str) -> HttpModelBackend:
        oracle = select_oracle(organism)
        if oracle == "alphagenome":
            return self.alphagenome
        if oracle == "evo2":
            return self.evo2
        raise ValueError(f"no sequence-model worker supports organism {organism!r}")
