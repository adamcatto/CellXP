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
    EntityBackend,
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
from .ensembl import EnsemblRestBackend

__all__ = [
    # genome service + catalog
    "ReferenceGenomeService",
    "ASSEMBLY_CATALOG",
    "SPECIES_PROFILES",
    "AssemblyInfo",
    "ContigInfo",
    "SpeciesProfile",
    "SequenceBackend",
    "EntityBackend",
    "LiftoverBackend",
    "EnsemblRestBackend",
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
