"""Motif-scan request/result types for the Binding Service (BIS-1).

Every motif claim records the motif database name, release version, and motif ID
so claims are reproducible and versioned (BIS-1, `specs/services/binding_service.md`).
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from cellxp.domain.enums import Strand


class MotifHit(BaseModel):
    """A single FIMO/JASPAR motif match."""

    motif_id: str      # e.g. "MA0107.1" (JASPAR stable ID)
    motif_name: str    # e.g. "RELA"
    tf: str            # TF name
    chrom: str | None = None
    start: int | None = None  # canonical 0-based within the submitted window
    end: int | None = None
    strand: Strand = Strand.UNSTRANDED
    score: float       # log-odds or p-value converted score
    p_value: float | None = None
    motif_db: str = "JASPAR"
    motif_db_release: str = "unknown"


class MotifScanRequest(BaseModel):
    """Request to scan a sequence or genomic interval for TF-binding motifs."""

    sequence: str | None = None               # raw DNA sequence to scan
    chrom: str | None = None                  # alternatively, specify a genomic interval
    start: int | None = None
    end: int | None = None
    organism: str
    assembly: str | None = None
    motif_db: str = "JASPAR"                  # version pinned in provenance (BIS-1)
    tfs: list[str] | None = None              # restrict to TF set; None = full panel
    p_value_threshold: float = 1e-4


class MotifScanResult(BaseModel):
    """Results from a motif scan (BIS-5: no hits is a valid empty result, not an error)."""

    hits: list[MotifHit] = Field(default_factory=list)
    motif_db: str = "JASPAR"
    motif_db_release: str = "unknown"
    n_sequences_scanned: int = 0
    skipped_tfs: list[str] = Field(default_factory=list)  # TFs not in the motif DB
