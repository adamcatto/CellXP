"""Canonical positioned domain types for CellXP.

`GenomicInterval` and `Variant` are the canonical positioned entities
(`coordinate_systems.md` §2). Their coordinates are **always** the internal canonical
representation: 0-based half-open `[start, end)` for intervals; canonical 0-based for
variant positions. Edge formats are converted via `domain/coordinates.py` before
construction.

These models enforce only the **intrinsic** invariants that need no external data (strand
vocabulary, non-negative coordinates). Invariants that need a reference (contig bounds,
assembly recognition, reference-allele match) live in `domain/validators/coordinates.py`
because they require the reference service.
"""

from __future__ import annotations

from pydantic import BaseModel, field_validator

from .enums import Strand
from .evidence import EvidenceItem  # re-exported: canonical shape lives in domain/evidence.py

__all__ = ["EvidenceItem", "GenomicInterval", "Variant"]


class GenomicInterval(BaseModel):
    """A canonical 0-based half-open genomic interval.

    `start >= end` is permitted only as a circular origin-crossing interval and is checked
    against assembly topology by `validators.coordinates.validate_interval`.
    """

    species: str | None = None
    assembly: str | None = None
    chrom: str
    start: int
    end: int
    strand: Strand = Strand.UNSTRANDED

    @field_validator("start", "end")
    @classmethod
    def _non_negative(cls, v: int) -> int:
        if v < 0:
            raise ValueError("genomic coordinates must be non-negative (canonical 0-based)")
        return v


class Variant(BaseModel):
    """A variant at a canonical 0-based position with explicit assembly identity."""

    chrom: str
    pos: int
    ref: str
    alt: str
    assembly: str | None = None
    rsid: str | None = None

    @field_validator("pos")
    @classmethod
    def _non_negative(cls, v: int) -> int:
        if v < 0:
            raise ValueError("variant position must be non-negative (canonical 0-based)")
        return v
