"""Reference genome service package (N4).

Importing this package registers `ReferenceGenomeService` in the global service registry.
"""

from .annotations import AnnotationFeature, AnnotationRequest, AnnotationResult
from .ensembl import EnsemblRestBackend
from .genome import (
    ASSEMBLY_CATALOG,
    SPECIES_PROFILES,
    AssemblyInfo,
    ContigInfo,
    EntityBackend,
    EntityResolveRequest,
    EntityResolveResult,
    LiftoverBackend,
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
    "ASSEMBLY_CATALOG",
    "SPECIES_PROFILES",
    "AnnotationFeature",
    "AnnotationRequest",
    "AnnotationResult",
    "AssemblyInfo",
    "ContigInfo",
    "EnsemblRestBackend",
    "EntityBackend",
    "EntityResolveRequest",
    "EntityResolveResult",
    "LiftoverBackend",
    "LiftoverRequest",
    "LiftoverResult",
    "LiftoverSegment",
    "ReferenceCatalog",
    "ReferenceGenomeService",
    "ResolvedEntity",
    "SequenceBackend",
    "SequenceFetchRequest",
    "SequenceFetchResult",
    "SpeciesProfile",
    "VariantValidationRequest",
    "VariantValidationResult",
]
