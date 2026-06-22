"""CRISPR service package (X5). Importing it registers CrisprService."""

from .schemas import (
    CrisprBackend, CrisprRequest, CrisprResult, EditOutcomeRequest, EditOutcomeResult, EditSpec,
    Guide, GuideScoringRequest, GuideScoringResult, OffTarget, OffTargetRequest, OffTargetResult,
)
from .service import CrisprService
from .backends import (
    DeterministicCrisprBackend, HttpCrisprBackend, crispr_backend_from_environment,
)

__all__ = [
    "CrisprService", "CrisprBackend", "CrisprRequest", "CrisprResult", "EditSpec", "Guide",
    "OffTarget", "OffTargetRequest", "OffTargetResult", "GuideScoringRequest",
    "GuideScoringResult", "EditOutcomeRequest", "EditOutcomeResult",
    "DeterministicCrisprBackend", "HttpCrisprBackend", "crispr_backend_from_environment",
]
