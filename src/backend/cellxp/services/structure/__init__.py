"""Structure service package (X3).

Importing this package registers `StructureService` in the global service registry.
"""

from .backends import (
    BOLTZ_MODEL_VERSION,
    ESMFOLD_REPOSITORY,
    ESMFOLD_REVISION,
    ProductionStructureBackend,
    RemoteStructureBackend,
    StructureRuntimeConfig,
)
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
    "BOLTZ_MODEL_VERSION",
    "ESMFOLD_MAX_RESIDUES",
    "ESMFOLD_REPOSITORY",
    "ESMFOLD_REVISION",
    "LOW_CONFIDENCE_THRESHOLD",
    "ContactMapRequest",
    "ContactMapResult",
    "DnaShapeRequest",
    "DnaShapeResult",
    "LigandSpec",
    "ProductionStructureBackend",
    "RemoteStructureBackend",
    "Span",
    "StructureBackend",
    "StructureKind",
    "StructureRequest",
    "StructureResult",
    "StructureRuntimeConfig",
    "StructureService",
    "classify_structure_task",
    "low_confidence_spans",
    "mean_confidence_band",
    "select_structure_model",
    "validate_kind_alphabet",
]
