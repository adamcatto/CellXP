"""GWAS/QTL service package (X1, FR-14)."""

from __future__ import annotations

from .backends import (
    DeterministicGwasBackend,
    EbiGwasQtlBackend,
    HttpGwasBackend,
    OpenTargetsGwasBackend,
    gwas_backend_from_environment,
)
from .schemas import (
    Association,
    ColocBatchResult,
    ColocRequest,
    ColocResult,
    CredibleSet,
    CredibleVariant,
    FineMapRequest,
    FineMapResult,
    GeneReference,
    GwasBackend,
    GwasRequest,
    GwasResult,
    LdPair,
    LdRequest,
    LdResult,
)
from .service import GwasService

__all__ = [
    "Association",
    "ColocBatchResult",
    "ColocRequest",
    "ColocResult",
    "CredibleSet",
    "CredibleVariant",
    "DeterministicGwasBackend",
    "EbiGwasQtlBackend",
    "FineMapRequest",
    "FineMapResult",
    "GeneReference",
    "GwasBackend",
    "GwasRequest",
    "GwasResult",
    "GwasService",
    "HttpGwasBackend",
    "LdPair",
    "LdRequest",
    "LdResult",
    "OpenTargetsGwasBackend",
    "gwas_backend_from_environment",
]
