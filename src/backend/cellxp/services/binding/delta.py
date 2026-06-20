"""Binding-delta request/result types (BIS-3 — variant occupancy changes).

Variant-induced binding changes are the "FR-14 binding subset" of N5: when a variant
is supplied to the binding service, the pipeline computes occupancy/binding deltas
(gain/loss of TF sites) between the reference and alternate sequences (BIS-3).
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from cellxp.domain.enums import Strand
from cellxp.domain.evidence import Confidence, Provenance
from cellxp.domain.models import Variant


class BindingPred(BaseModel):
    """Predicted TF binding at a position in the sequence window."""

    tf: str
    score: float         # occupancy score (0–1 or log-scale depending on model)
    position: int        # 0-based offset within the sequence window
    strand: Strand = Strand.UNSTRANDED
    model: str = "unknown"


class BindingDelta(BaseModel):
    """Per-TF change in occupancy between alt and ref: `delta = occupancy(alt) − occupancy(ref)`."""

    tf: str
    value: float
    direction: Literal["gain", "loss", "neutral"]


class BindingDeltaRequest(BaseModel):
    """Request to score the binding-occupancy delta induced by a variant (BIS-3)."""

    variant: Variant
    organism: str
    assembly: str
    window_bp: int = 200           # short window around the variant for motif scanning
    tfs: list[str] | None = None   # restrict to TF set; None = full panel
    motif_db: str = "JASPAR"


class BindingDeltaResult(BaseModel):
    """Binding-delta result (BIS-3/5)."""

    deltas: list[BindingDelta] = Field(default_factory=list)
    ref_binding: list[BindingPred] = Field(default_factory=list)
    alt_binding: list[BindingPred] = Field(default_factory=list)
    confidence: Confidence
    provenance: Provenance = Field(default_factory=Provenance)


# ---------------------------------------------------------------------------
# Convenience: BindingResult for predict_binding (used by binding subgraph)
# ---------------------------------------------------------------------------


class BindingResult(BaseModel):
    """Full binding prediction result (`binding_site_prediction.md` §5)."""

    binding: list[BindingPred] = Field(default_factory=list)
    motif_hits: list[dict] = Field(default_factory=list)   # MotifHit serialized as dict
    deltas: list[BindingDelta] | None = None               # present only when variant supplied
    confidence: Confidence
    provenance: Provenance = Field(default_factory=Provenance)


class BindingRequest(BaseModel):
    """Inputs for predict_binding (`binding_site_prediction.md` §2)."""

    sequence: str | None = None          # raw DNA sequence
    chrom: str | None = None             # alternatively, a genomic interval
    start: int | None = None
    end: int | None = None
    organism: str
    assembly: str | None = None
    variant: Variant | None = None       # if present → compute deltas
    tfs: list[str] | None = None
    motif_db: str = "JASPAR"
