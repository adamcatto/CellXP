"""AlphaGenome worker server with strict mammalian applicability checks."""

from __future__ import annotations

import hashlib

from fastapi import FastAPI

from cellxp.domain.enums import ConfidenceBand
from cellxp.domain.evidence import Confidence

from .schemas import (
    AssayDelta,
    SpliceEffectRequest,
    SpliceEffectResult,
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

MANIFEST = load_manifest("alphagenome")
app = FastAPI(title="CellXP AlphaGenome worker", version="1")


@app.get("/health")
def health() -> dict[str, object]:
    return health_payload(MANIFEST)


@app.get("/version")
def version() -> dict[str, object]:
    return MANIFEST.model_dump(mode="json")


@app.post("/v1/score-variants", response_model=VariantEffectResult)
def score_variants(request: VariantEffectRequest) -> VariantEffectResult:
    enforce_model_organism("alphagenome", request.organism)
    if not fixture_mode():
        return call_production("alphagenome", "score_variants", request)
    effects = []
    for variant in request.variants:
        variant_id = f"{variant.chrom}:{variant.pos + 1}:{variant.ref}>{variant.alt}"
        value = (_unit_score(variant_id) - 0.5) * 2
        delta = AssayDelta(
            assay=(request.assays or ["RNA_SEQ"])[0],
            tissue=request.tissues[0] if request.tissues else None,
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
    enforce_model_organism("alphagenome", request.organism)
    if not fixture_mode():
        return call_production("alphagenome", "predict_tracks", request)
    assays = request.assays or ["RNA_SEQ"]
    return TrackPredictionResult(
        tracks={assay: [_unit_score(f"{assay}:{i}") for i in range(8)] for assay in assays},
        model=f"alphagenome@{MANIFEST.model_revision}",
        confidence=Confidence(band=ConfidenceBand.MEDIUM, score=0.5),
    )


@app.post("/v1/score-splicing", response_model=SpliceEffectResult)
def score_splicing(request: SpliceEffectRequest) -> SpliceEffectResult:
    enforce_model_organism("alphagenome", request.organism)
    if not fixture_mode():
        return call_production("alphagenome", "score_splicing", request)
    return SpliceEffectResult(
        donor_gain=_unit_score(f"{request.variant.chrom}:{request.variant.pos}"),
        confidence=Confidence(band=ConfidenceBand.MEDIUM, score=0.5),
    )


def _unit_score(value: str) -> float:
    return int(hashlib.sha256(value.encode()).hexdigest()[:8], 16) / 0xFFFFFFFF
