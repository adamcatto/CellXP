"""Liftover request/response types for the Reference Genome Service.

Coordinate-convention conversions and cross-assembly lifts are provenance-bearing
steps (RGS-3): every call records the tool, source/target assemblies, and any
unmapped segments so the transform is fully auditable.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from cellxp.domain.models import GenomicInterval


class LiftoverSegment(BaseModel):
    """One interval from the source assembly with its target mapping (or failure)."""

    source_chrom: str
    source_start: int  # canonical 0-based
    source_end: int    # canonical 0-based half-open
    target_chrom: str | None = None
    target_start: int | None = None  # canonical 0-based
    target_end: int | None = None    # canonical 0-based half-open
    mapped: bool
    fail_reason: str | None = None


class LiftoverRequest(BaseModel):
    """Request to lift intervals from one assembly to another."""

    intervals: list[GenomicInterval]
    source_assembly: str
    target_assembly: str
    organism: str


class LiftoverResult(BaseModel):
    """Liftover result with per-segment mapping outcomes (RGS-3)."""

    source_assembly: str
    target_assembly: str
    organism: str
    segments: list[LiftoverSegment] = Field(default_factory=list)
    mapped_count: int = 0
    unmapped_count: int = 0
