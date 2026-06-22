"""GWAS/QTL service package (X1, FR-14)."""

from __future__ import annotations

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
from .backends import (
    DeterministicGwasBackend, EbiGwasQtlBackend, HttpGwasBackend, gwas_backend_from_environment,
)

__all__ = [
    "Association",
    "ColocBatchResult",
    "ColocRequest",
    "ColocResult",
    "CredibleSet",
    "CredibleVariant",
    "FineMapRequest",
    "FineMapResult",
    "GeneReference",
    "GwasBackend",
    "GwasRequest",
    "GwasResult",
    "GwasService",
    "LdPair",
    "LdRequest",
    "LdResult",
    "DeterministicGwasBackend",
    "EbiGwasQtlBackend",
    "HttpGwasBackend",
    "gwas_backend_from_environment",
]
