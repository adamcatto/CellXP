"""CRISPR service package (X5). Importing it registers CrisprService."""

from .backends import (
    DeterministicCrisprBackend,
    HttpCrisprBackend,
    crispr_backend_from_environment,
)
from .schemas import (
    CrisprBackend,
    CrisprRequest,
    CrisprResult,
    EditOutcomeRequest,
    EditOutcomeResult,
    EditSpec,
    Guide,
    GuideScoringRequest,
    GuideScoringResult,
    OffTarget,
    OffTargetRequest,
    OffTargetResult,
)
from .service import CrisprService

__all__ = [
    "CrisprBackend",
    "CrisprRequest",
    "CrisprResult",
    "CrisprService",
    "DeterministicCrisprBackend",
    "EditOutcomeRequest",
    "EditOutcomeResult",
    "EditSpec",
    "Guide",
    "GuideScoringRequest",
    "GuideScoringResult",
    "HttpCrisprBackend",
    "OffTarget",
    "OffTargetRequest",
    "OffTargetResult",
    "crispr_backend_from_environment",
]
