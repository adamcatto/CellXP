"""AlphaGenome / sequence-model service (N5).

Wraps AlphaGenome-class (mammalian) and Evo 2-class (broad-clade) sequence models
behind one stable service boundary (AGS-1..5, `specs/services/alphagenome_service.md`).

A `ModelBackend` can be injected at construction for production deployment; when absent
every operation returns `ServiceOutcome.UNSUPPORTED` so the agent can report honestly
rather than crashing (same philosophy as the reference genome service).
"""

from __future__ import annotations

import hashlib
import json

from pydantic import BaseModel

from cellxp.agent.state import RunError, Step
from cellxp.domain.clock import utc_now_iso
from cellxp.domain.enums import ConfidenceBand, SourceKind, TaskStatus
from cellxp.domain.evidence import Confidence, EvidenceItem, Provenance
from cellxp.services.base import Service, ServiceResult
from cellxp.services.registry import registry

from .schemas import (
    ModelBackend,
    SequenceScoringRequest,
    SequenceScoringResult,
    SpliceEffectRequest,
    SpliceEffectResult,
    TrackPredictionRequest,
    TrackPredictionResult,
    VariantEffectRequest,
    VariantEffectResult,
    alphagenome_applicable,
    organism_class_for,
    select_oracle,
)


@registry.register
class AlphaGenomeService(Service):
    """Organism-routing sequence model service (AlphaGenome / Evo 2 / SpliceAI).

    `model_backend` is the injected implementation. Without one, all operations
    return UNSUPPORTED so the agent can surface a clear "model not configured" message
    rather than propagating a runtime error.
    """

    name = "alphagenome"

    def __init__(self, *, model_backend: ModelBackend | None = None) -> None:
        self._backend = model_backend

    # ------------------------------------------------------------------
    # score_variants (FR-13, AGS-1/2/4)
    # ------------------------------------------------------------------

    def score_variants(
        self, request: VariantEffectRequest
    ) -> ServiceResult[VariantEffectResult]:
        """Predict per-assay/tissue deltas for each variant (FR-13).

        Enforces AGS-1: AlphaGenome is called only for mammalian organisms;
        other clades require an Evo 2 backend. Mismatches return UNSUPPORTED.
        """
        started = utc_now_iso()

        oracle = select_oracle(request.organism)
        if oracle == "unsupported":
            return ServiceResult.unsupported(
                f"no applicable sequence oracle for organism {request.organism!r}; "
                f"add it to the species catalog first",
                steps=[_done_step("score_variants", started, tool="alphagenome_router")],
            )

        if oracle == "alphagenome" and not alphagenome_applicable(request.organism):
            return ServiceResult.unsupported(
                f"AlphaGenome mammalian heads are not applicable to {request.organism!r} "
                f"(AGS-1); use an Evo 2 backend for this organism class",
                steps=[_done_step("score_variants", started, tool="alphagenome_router")],
            )

        if self._backend is None:
            return ServiceResult.unsupported(
                f"score_variants requires a {oracle!r} model backend; none is configured",
                steps=[_done_step("score_variants", started, tool="alphagenome_router")],
            )

        try:
            raw = self._backend.score_variants(request)
        except Exception as exc:  # noqa: BLE001
            return ServiceResult.failed(
                RunError(kind="BackendError", message=str(exc)),
                steps=[_failed_step("score_variants", started, tool=oracle, error=str(exc))],
            )

        finished = utc_now_iso()
        provenance = _call_provenance(
            request, raw, tool=oracle, version=_backend_version(self._backend), timestamp=finished
        )
        evidence = [
            EvidenceItem(
                source=oracle,
                source_kind=SourceKind.MODEL,
                claim=f"Variant effect predicted for {len(raw.per_variant)} variant(s) via {oracle}",
                confidence=Confidence(band=ConfidenceBand.MEDIUM),
                provenance=provenance,
            )
        ]
        return ServiceResult.succeeded(
            raw,
            steps=[_done_step(
                "score_variants", started, tool=oracle, finished=finished,
                tool_version=_backend_version(self._backend),
            )],
            evidence=evidence,
        )

    # ------------------------------------------------------------------
    # score_sequences (Evo 2 — all clades)
    # ------------------------------------------------------------------

    def score_sequences(
        self, request: SequenceScoringRequest
    ) -> ServiceResult[SequenceScoringResult]:
        """Score raw DNA sequences for likelihood or embeddings (Evo 2 / AlphaGenome)."""
        started = utc_now_iso()

        if organism_class_for(request.organism) is None:
            return ServiceResult.unsupported(
                f"organism {request.organism!r} not in species catalog",
                steps=[_done_step("score_sequences", started, tool="alphagenome_router")],
            )

        if self._backend is None:
            return ServiceResult.unsupported(
                "score_sequences requires a model backend; none is configured",
                steps=[_done_step("score_sequences", started, tool="alphagenome_router")],
            )

        try:
            raw = self._backend.score_sequences(request)
        except Exception as exc:  # noqa: BLE001
            return ServiceResult.failed(
                RunError(kind="BackendError", message=str(exc)),
                steps=[_failed_step("score_sequences", started, tool="model_backend", error=str(exc))],
            )

        finished = utc_now_iso()
        version = _backend_version(self._backend)
        return ServiceResult.succeeded(
            raw,
            steps=[_done_step(
                "score_sequences", started, tool="model_backend",
                tool_version=version, finished=finished,
            )],
            evidence=[_model_evidence(
                claim=f"Scored {len(request.sequences)} sequence(s)",
                confidence=raw.confidence or Confidence(band=ConfidenceBand.MEDIUM),
                request=request, result=raw, tool="model_backend", version=version,
                timestamp=finished,
            )],
        )

    # ------------------------------------------------------------------
    # predict_tracks
    # ------------------------------------------------------------------

    def predict_tracks(
        self, request: TrackPredictionRequest
    ) -> ServiceResult[TrackPredictionResult]:
        """Predict regulatory/functional tracks across a genomic interval (AGS-3)."""
        started = utc_now_iso()

        oracle = select_oracle(request.organism)
        if oracle == "unsupported":
            return ServiceResult.unsupported(
                f"no oracle for organism {request.organism!r}",
                steps=[_done_step("predict_tracks", started, tool="alphagenome_router")],
            )

        if self._backend is None:
            return ServiceResult.unsupported(
                "predict_tracks requires a model backend; none is configured",
                steps=[_done_step("predict_tracks", started, tool="alphagenome_router")],
            )

        try:
            raw = self._backend.predict_tracks(request)
        except Exception as exc:  # noqa: BLE001
            return ServiceResult.failed(
                RunError(kind="BackendError", message=str(exc)),
                steps=[_failed_step("predict_tracks", started, tool=oracle, error=str(exc))],
            )

        finished = utc_now_iso()
        version = _backend_version(self._backend)
        return ServiceResult.succeeded(
            raw,
            steps=[_done_step(
                "predict_tracks", started, tool=oracle,
                tool_version=version, finished=finished,
            )],
            evidence=[_model_evidence(
                claim=f"Predicted {len(raw.tracks)} track(s) via {oracle}",
                confidence=raw.confidence or Confidence(band=ConfidenceBand.MEDIUM),
                request=request, result=raw, tool=oracle, version=version,
                timestamp=finished,
            )],
        )

    # ------------------------------------------------------------------
    # score_splicing (SpliceAI — mammalian only)
    # ------------------------------------------------------------------

    def score_splicing(
        self, request: SpliceEffectRequest
    ) -> ServiceResult[SpliceEffectResult]:
        """Predict splice-altering effect via SpliceAI (mammalian only)."""
        started = utc_now_iso()

        if not alphagenome_applicable(request.organism):
            return ServiceResult.unsupported(
                f"SpliceAI is only applicable to mammalian organisms (got {request.organism!r})",
                steps=[_done_step("score_splicing", started, tool="spliceai_router")],
            )

        if self._backend is None:
            return ServiceResult.unsupported(
                "score_splicing requires a SpliceAI backend; none is configured",
                steps=[_done_step("score_splicing", started, tool="spliceai_router")],
            )

        try:
            raw = self._backend.score_splicing(request)
        except Exception as exc:  # noqa: BLE001
            return ServiceResult.failed(
                RunError(kind="BackendError", message=str(exc)),
                steps=[_failed_step("score_splicing", started, tool="spliceai", error=str(exc))],
            )

        finished = utc_now_iso()
        version = _backend_version(self._backend)
        return ServiceResult.succeeded(
            raw,
            steps=[_done_step(
                "score_splicing", started, tool="spliceai",
                tool_version=version, finished=finished,
            )],
            evidence=[_model_evidence(
                claim="Predicted splice effect via spliceai",
                confidence=raw.confidence,
                request=request, result=raw, tool="spliceai", version=version,
                timestamp=finished,
            )],
        )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _done_step(
    name: str,
    started: str,
    *,
    tool: str,
    finished: str | None = None,
    tool_version: str | None = None,
) -> Step:
    return Step(
        name=name,
        tool=tool,
        tool_version=tool_version,
        weight="light",
        status=TaskStatus.DONE,
        started_at=started,
        finished_at=finished or utc_now_iso(),
    )


def _backend_version(backend: ModelBackend) -> str:
    return str(getattr(backend, "version", "unknown"))


def _model_evidence(
    *,
    claim: str,
    confidence: Confidence,
    request: BaseModel,
    result: BaseModel,
    tool: str,
    version: str,
    timestamp: str,
) -> EvidenceItem:
    return EvidenceItem(
        source=tool,
        source_kind=SourceKind.MODEL,
        claim=claim,
        confidence=confidence,
        provenance=_call_provenance(
            request, result, tool=tool, version=version, timestamp=timestamp
        ),
    )


def _call_provenance(
    request: BaseModel,
    result: BaseModel,
    *,
    tool: str,
    version: str,
    timestamp: str,
) -> Provenance:
    request_json = request.model_dump_json()
    result_json = result.model_dump_json()
    inputs = request.model_dump(mode="json", exclude={"sequences"})
    if isinstance(request, SequenceScoringRequest):
        inputs["sequence_hashes"] = [
            hashlib.sha256(sequence.encode()).hexdigest() for sequence in request.sequences
        ]
        inputs["n_sequences"] = len(request.sequences)
    return Provenance(
        tool=tool,
        tool_version=version,
        inputs=json.loads(json.dumps(inputs, sort_keys=True)),
        timestamp=timestamp,
        input_hash=hashlib.sha256(request_json.encode()).hexdigest(),
        output_hash=hashlib.sha256(result_json.encode()).hexdigest(),
    )


def _failed_step(name: str, started: str, *, tool: str, error: str) -> Step:
    return Step(
        name=name,
        tool=tool,
        weight="light",
        status=TaskStatus.FAILED,
        started_at=started,
        finished_at=utc_now_iso(),
        error=error,
    )
