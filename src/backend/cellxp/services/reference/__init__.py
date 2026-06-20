"""Reference genome service package (N4).

Importing this package registers `ReferenceGenomeService` in the global service registry.
"""

from .annotations import AnnotationFeature, AnnotationRequest, AnnotationResult
from .genome import (
    ASSEMBLY_CATALOG,
    SPECIES_PROFILES,
    AssemblyInfo,
    ContigInfo,
    EntityResolveRequest,
    EntityResolveResult,
    ReferenceCatalog,
    ReferenceGenomeService,
    ResolvedEntity,
    SequenceBackend,
    SequenceFetchRequest,
    SequenceFetchResult,
    SpeciesProfile,
    VariantValidationRequest,
    VariantValidationResult,
)
from .liftover import LiftoverRequest, LiftoverResult, LiftoverSegment

__all__ = [
    # genome service + catalog
    "ReferenceGenomeService",
    "ASSEMBLY_CATALOG",
    "SPECIES_PROFILES",
    "AssemblyInfo",
    "ContigInfo",
    "SpeciesProfile",
    "SequenceBackend",
    # request / result types
    "EntityResolveRequest",
    "EntityResolveResult",
    "ResolvedEntity",
    "SequenceFetchRequest",
    "SequenceFetchResult",
    "VariantValidationRequest",
    "VariantValidationResult",
    "ReferenceCatalog",
    "LiftoverRequest",
    "LiftoverResult",
    "LiftoverSegment",
    "AnnotationRequest",
    "AnnotationResult",
    "AnnotationFeature",
]
