"""Evo 2 worker server for broad-clade DNA sequence scoring."""

from __future__ import annotations

import hashlib

from fastapi import FastAPI, HTTPException

from cellxp.domain.enums import ConfidenceBand
from cellxp.domain.evidence import Confidence

from .schemas import (
    AssayDelta,
    SequenceScoringRequest,
    SequenceScoringResult,
    TrackPredictionRequest,
    TrackPredictionResult,
    VariantEffect,
    VariantEffectRequest,
    VariantEffectResult,
)
from .worker_common import (
    call_production,
    enforce_model_organism,
    fixture_mode,
    health_payload,
    load_manifest,
)

MANIFEST = load_manifest("evo2")
app = FastAPI(title="CellXP Evo 2 worker", version="1")


@app.get("/health")
def health() -> dict[str, object]:
    return health_payload(MANIFEST)


@app.get("/version")
def version() -> dict[str, object]:
    return MANIFEST.model_dump(mode="json")


@app.post("/v1/score-sequences", response_model=SequenceScoringResult)
def score_sequences(request: SequenceScoringRequest) -> SequenceScoringResult:
    enforce_model_organism("evo2", request.organism)
    if not fixture_mode():
        return call_production("evo2", "score_sequences", request)
    normalized = [sequence.upper() for sequence in request.sequences]
    if any(not sequence or set(sequence) - set("ACGTN") for sequence in normalized):
        raise HTTPException(status_code=422, detail="sequences must use the DNA alphabet A/C/G/T/N")
    scores = [
        int(hashlib.sha256(sequence.encode()).hexdigest()[:8], 16) / 0xFFFFFFFF
        for sequence in normalized
    ]
    embeddings = [[score, 1.0 - score] for score in scores]
    return SequenceScoringResult(
        scores=scores,
        embeddings=embeddings if request.scoring_type == "embedding" else None,
        model=f"evo2@{MANIFEST.model_revision}",
        confidence=Confidence(band=ConfidenceBand.MEDIUM, score=0.5),
    )


@app.post("/v1/score-variants", response_model=VariantEffectResult)
def score_variants(request: VariantEffectRequest) -> VariantEffectResult:
    enforce_model_organism("evo2", request.organism)
    if not fixture_mode():
        return call_production("evo2", "score_variants", request)
    effects = []
    for variant in request.variants:
        variant_id = f"{variant.chrom}:{variant.pos + 1}:{variant.ref}>{variant.alt}"
        value = _unit_score(variant_id) - 0.5
        delta = AssayDelta(
            assay=(request.assays or ["sequence_likelihood"])[0],
            value=value,
            direction="up" if value > 0 else "down",
        )
        effects.append(VariantEffect(
            variant_id=variant_id,
            deltas=[delta],
            top_effects=[delta],
            confidence=Confidence(band=ConfidenceBand.MEDIUM, score=0.5),
        ))
    return VariantEffectResult(per_variant=effects)


@app.post("/v1/predict-tracks", response_model=TrackPredictionResult)
def predict_tracks(request: TrackPredictionRequest) -> TrackPredictionResult:
    enforce_model_organism("evo2", request.organism)
    if not fixture_mode():
        return call_production("evo2", "predict_tracks", request)
    assays = request.assays or ["sequence_likelihood"]
    return TrackPredictionResult(
        tracks={assay: [_unit_score(f"{assay}:{i}") for i in range(8)] for assay in assays},
        model=f"evo2@{MANIFEST.model_revision}",
        confidence=Confidence(band=ConfidenceBand.MEDIUM, score=0.5),
    )


def _unit_score(value: str) -> float:
    return int(hashlib.sha256(value.encode()).hexdigest()[:8], 16) / 0xFFFFFFFF
