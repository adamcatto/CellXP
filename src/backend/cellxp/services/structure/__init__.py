"""Structure service package (X3).

Importing this package registers `StructureService` in the global service registry.
"""

from .schemas import (
    ESMFOLD_MAX_RESIDUES,
    LOW_CONFIDENCE_THRESHOLD,
    ContactMapRequest,
    ContactMapResult,
    DnaShapeRequest,
    DnaShapeResult,
    LigandSpec,
    Span,
    StructureBackend,
    StructureKind,
    StructureRequest,
    StructureResult,
)
from .service import StructureService
from .transforms import (
    classify_structure_task,
    low_confidence_spans,
    mean_confidence_band,
    select_structure_model,
    validate_kind_alphabet,
)

__all__ = [
    "StructureService",
    # request/result types
    "StructureRequest",
    "StructureResult",
    "ContactMapRequest",
    "ContactMapResult",
    "DnaShapeRequest",
    "DnaShapeResult",
    # value types
    "LigandSpec",
    "Span",
    "StructureKind",
    "StructureBackend",
    # constants
    "ESMFOLD_MAX_RESIDUES",
    "LOW_CONFIDENCE_THRESHOLD",
    # transforms
    "classify_structure_task",
    "validate_kind_alphabet",
    "select_structure_model",
    "low_confidence_spans",
    "mean_confidence_band",
]
