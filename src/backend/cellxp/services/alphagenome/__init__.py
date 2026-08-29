"""AlphaGenome / sequence-model service package (N5).

Importing this package registers `AlphaGenomeService` in the global service registry.
"""

from .client import AlphaGenomeService
from .http_backend import HttpModelBackend, RoutedHttpModelBackend
from .schemas import (
    ALPHAGENOME_SUPPORTED_CLASSES,
    EVO2_SUPPORTED_CLASSES,
    AssayDelta,
    ModelBackend,
    SequenceScoringRequest,
    SequenceScoringResult,
    SpliceEffectRequest,
    SpliceEffectResult,
    TrackPredictionRequest,
    TrackPredictionResult,
    VariantEffect,
    VariantEffectRequest,
    VariantEffectResult,
    alphagenome_applicable,
    organism_class_for,
    select_oracle,
)
from .transforms import (
    DEFAULT_WINDOW_BP,
    compute_deltas,
    frame_sequence_window,
    pos_in_window,
    substitute_allele,
    variant_id,
)

__all__ = [
    "ALPHAGENOME_SUPPORTED_CLASSES",
    "DEFAULT_WINDOW_BP",
    "EVO2_SUPPORTED_CLASSES",
    "AlphaGenomeService",
    "AssayDelta",
    "HttpModelBackend",
    "ModelBackend",
    "RoutedHttpModelBackend",
    "SequenceScoringRequest",
    "SequenceScoringResult",
    "SpliceEffectRequest",
    "SpliceEffectResult",
    "TrackPredictionRequest",
    "TrackPredictionResult",
    "VariantEffect",
    "VariantEffectRequest",
    "VariantEffectResult",
    "alphagenome_applicable",
    "compute_deltas",
    "frame_sequence_window",
    "organism_class_for",
    "pos_in_window",
    "select_oracle",
    "substitute_allele",
    "variant_id",
]
