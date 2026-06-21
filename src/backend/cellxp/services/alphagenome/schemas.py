"""AlphaGenome / sequence-model service request and result types.

All request types carry `organism` and `assembly` so the service can enforce
organism-appropriate model selection (AGS-1) and record complete provenance (AGS-2).
Large track/embedding outputs are referenced via `storage_ref` rather than inlined
to satisfy AGS-3.
"""

from __future__ import annotations

from typing import Literal, Protocol, runtime_checkable

from pydantic import BaseModel, Field

from cellxp.domain.enums import OrganismClass
from cellxp.domain.evidence import Confidence, Provenance
from cellxp.domain.models import GenomicInterval, Variant


# ---------------------------------------------------------------------------
# Variant-effect types (FR-13)
# ---------------------------------------------------------------------------


class AssayDelta(BaseModel):
    """Per-assay/tissue effect of a variant: `delta = f(alt) - f(ref)`."""

    assay: str
    tissue: str | None = None
    value: float
    direction: Literal["up", "down", "none"]


class VariantEffect(BaseModel):
    """Full per-variant effect summary (`variant_effect_prediction.md` §5)."""

    variant_id: str  # canonical chrom:pos:ref>alt
    deltas: list[AssayDelta] = Field(default_factory=list)
    top_effects: list[AssayDelta] = Field(default_factory=list)
    nearest_gene: str | None = None
    regulatory_context: str | None = None
    confidence: Confidence
    provenance: Provenance = Field(default_factory=Provenance)


class VariantEffectRequest(BaseModel):
    """Inputs for variant-effect scoring (`variant_effect_prediction.md` §2)."""

    variants: list[Variant]
    organism: str
    assembly: str
    assays: list[str] | None = None     # subset of supported_assays; None = model default
    tissues: list[str] | None = None
    window_bp: int | None = None        # context window; None = model default (131,072 for AlphaGenome)


class VariantEffectResult(BaseModel):
    per_variant: list[VariantEffect] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Sequence-scoring types (Evo 2, embeddings)
# ---------------------------------------------------------------------------


class SequenceScoringRequest(BaseModel):
    """Score raw DNA sequences for log-likelihood or embeddings."""

    sequences: list[str]
    organism: str
    assembly: str | None = None
    scoring_type: Literal["likelihood", "embedding"] = "likelihood"


class SequenceScoringResult(BaseModel):
    scores: list[float] = Field(default_factory=list)
    embeddings: list[list[float]] | None = None
    model: str = "unknown"
    confidence: Confidence | None = None


# ---------------------------------------------------------------------------
# Track-prediction types
# ---------------------------------------------------------------------------


class TrackPredictionRequest(BaseModel):
    """Predict regulatory/functional tracks across a genomic interval."""

    interval: GenomicInterval
    organism: str
    assembly: str
    assays: list[str] | None = None
    tissues: list[str] | None = None


class TrackPredictionResult(BaseModel):
    """Per-assay/tissue predicted tracks; large arrays go to object storage (AGS-3)."""

    tracks: dict[str, list[float]] = Field(default_factory=dict)  # assay → values
    storage_ref: str | None = None  # object-store key when payload exceeds inline limit
    model: str = "unknown"
    confidence: Confidence | None = None


# ---------------------------------------------------------------------------
# Splice-effect types (SpliceAI)
# ---------------------------------------------------------------------------


class SpliceEffectRequest(BaseModel):
    variant: Variant
    organism: str
    assembly: str


class SpliceEffectResult(BaseModel):
    donor_gain: float | None = None
    donor_loss: float | None = None
    acceptor_gain: float | None = None
    acceptor_loss: float | None = None
    confidence: Confidence
    provenance: Provenance = Field(default_factory=Provenance)


# ---------------------------------------------------------------------------
# Model backend protocol
# ---------------------------------------------------------------------------


@runtime_checkable
class ModelBackend(Protocol):
    """Injectable backend wrapping a real AlphaGenome/Evo 2/SpliceAI endpoint.

    Implementations handle HTTP/gRPC transport, batching, retries, and encoding;
    the service wraps them with provenance, confidence, and error handling.
    """

    def score_variants(self, request: VariantEffectRequest) -> VariantEffectResult: ...

    def score_sequences(
        self, request: SequenceScoringRequest
    ) -> SequenceScoringResult: ...

    def predict_tracks(
        self, request: TrackPredictionRequest
    ) -> TrackPredictionResult: ...

    def score_splicing(self, request: SpliceEffectRequest) -> SpliceEffectResult: ...


# ---------------------------------------------------------------------------
# Organism-applicability helpers
# ---------------------------------------------------------------------------

#: Organism classes supported by AlphaGenome mammalian heads.
ALPHAGENOME_SUPPORTED_CLASSES = frozenset({OrganismClass.MAMMALIAN})

#: All classes that support sequence-scoring via Evo 2 (broad applicability).
EVO2_SUPPORTED_CLASSES = frozenset(OrganismClass)


def organism_class_for(organism: str) -> OrganismClass | None:
    """Look up the organism class from the built-in species profiles.

    Returns None when the organism is not in the catalog; callers must treat
    the capability as unsupported rather than defaulting to mammalian (AGS-1).
    """
    from cellxp.services.reference.genome import SPECIES_PROFILES
    profile = SPECIES_PROFILES.get(organism)
    return profile.organism_class if profile else None


def alphagenome_applicable(organism: str) -> bool:
    """True only when AlphaGenome mammalian heads are valid for `organism`."""
    cls = organism_class_for(organism)
    return cls in ALPHAGENOME_SUPPORTED_CLASSES if cls is not None else False


def select_oracle(organism: str) -> Literal["alphagenome", "evo2", "unsupported"]:
    """Choose the appropriate sequence oracle for `organism` (AGS-1)."""
    cls = organism_class_for(organism)
    if cls is None:
        return "unsupported"
    if cls in ALPHAGENOME_SUPPORTED_CLASSES:
        return "alphagenome"
    if cls in EVO2_SUPPORTED_CLASSES:
        return "evo2"
    return "unsupported"
