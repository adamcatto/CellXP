"""Structure service request/result types and the injectable backend protocol (X3).

Covers the *prediction* surface of the structure service (`structure_service.md` §2):
protein / nucleic-acid / complex 3D structure (ESMFold / Boltz-2), chromatin contact maps
(Orca), and DNA shape (DNAshapeR). Generative design (`design_protein`, FR-18a) is
review-gated and out of scope for X3 — it lands with the human-review gate (X6).

Heavy outputs (coordinate files, contact-map payloads, shape tracks) are referenced via
`storage_ref` and never inlined (STS-2). Per-residue/per-position confidence is exposed
wherever the model provides it (STS-3); the service derives low-confidence spans from it.
"""

from __future__ import annotations

from typing import Literal, Protocol, runtime_checkable

from pydantic import BaseModel, Field, field_validator

from cellxp.domain.enums import ConfidenceBand
from cellxp.domain.evidence import Confidence, Provenance
from cellxp.domain.models import GenomicInterval
from cellxp.domain.sequences import BiologicalSequence

#: Structure-prediction task kinds (`structure_prediction.md` §2).
StructureKind = Literal["protein", "nucleic_acid", "complex", "dna_shape", "contacts"]

#: pLDDT-style per-residue confidence is recorded normalized to ``[0, 1]`` (pLDDT/100).
#: Residues at or below this value are flagged as low-confidence (AlphaFold's pLDDT<70).
LOW_CONFIDENCE_THRESHOLD = 0.70

#: Practical single-sequence length ceiling for ESMFold; longer chains route to Boltz-2
#: or return a validation error with the limit (`structure_prediction.md` §7).
ESMFOLD_MAX_RESIDUES = 2700


# ---------------------------------------------------------------------------
# Shared value types
# ---------------------------------------------------------------------------


class Span(BaseModel):
    """A half-open residue/position span ``[start, end)`` flagged on a structure."""

    start: int
    end: int
    label: str | None = None

    @field_validator("start", "end")
    @classmethod
    def _non_negative(cls, v: int) -> int:
        if v < 0:
            raise ValueError("span coordinates must be non-negative")
        return v


class LigandSpec(BaseModel):
    """A small-molecule binder for complex/affinity prediction (Boltz-2)."""

    format: Literal["smiles", "inchi", "ccd"]
    value: str

    @field_validator("value")
    @classmethod
    def _non_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("ligand value must be non-empty")
        return v.strip()


# ---------------------------------------------------------------------------
# predict_structure (protein / nucleic_acid / complex)
# ---------------------------------------------------------------------------


class StructureRequest(BaseModel):
    """Inputs for 3D structure prediction (`structure_prediction.md` §2)."""

    kind: Literal["protein", "nucleic_acid", "complex"]
    sequences: list[BiologicalSequence] = Field(default_factory=list)
    ligand: LigandSpec | None = None
    organism: str | None = None      # optional: structure models are sequence-based
    assembly: str | None = None


class StructureResult(BaseModel):
    """Predicted structure; heavy coordinates live in object storage via `structure_ref`.

    `per_residue_confidence` is pLDDT-style, normalized to ``[0, 1]``. The service derives
    `low_confidence_regions` and the summary `confidence` band from it; the backend need
    only populate `structure_ref`, `per_residue_confidence`, `affinity`, and `model`.
    """

    structure_ref: str | None = None             # storage_ref to mmCIF/PDB coords
    per_residue_confidence: list[float] | None = None
    affinity: float | None = None                # Boltz-2 protein–ligand
    low_confidence_regions: list[Span] = Field(default_factory=list)
    model: str = "unknown"
    confidence: Confidence = Field(
        default_factory=lambda: Confidence(band=ConfidenceBand.UNKNOWN)
    )
    provenance: Provenance = Field(default_factory=Provenance)


# ---------------------------------------------------------------------------
# predict_contacts (chromatin contact map — Orca)
# ---------------------------------------------------------------------------


class ContactMapRequest(BaseModel):
    """Inputs for chromatin contact-map prediction over a genomic interval."""

    interval: GenomicInterval
    organism: str
    assembly: str
    bin_size_bp: int | None = None   # None = model default


class ContactMapResult(BaseModel):
    """Contact-map payload referenced via object storage (STS-2)."""

    contacts_ref: str | None = None
    n_bins: int | None = None
    bin_size_bp: int | None = None
    model: str = "unknown"
    confidence: Confidence = Field(
        default_factory=lambda: Confidence(band=ConfidenceBand.UNKNOWN)
    )
    provenance: Provenance = Field(default_factory=Provenance)


# ---------------------------------------------------------------------------
# predict_dna_shape (minor-groove width / roll / etc. — DNAshapeR)
# ---------------------------------------------------------------------------


class DnaShapeRequest(BaseModel):
    """Inputs for DNA-shape prediction over a genomic interval."""

    interval: GenomicInterval
    organism: str
    assembly: str
    features: list[str] | None = None   # subset of shape params; None = model default


class DnaShapeResult(BaseModel):
    """DNA-shape track payload referenced via object storage (STS-2)."""

    shape_track_ref: str | None = None
    features: list[str] = Field(default_factory=list)   # e.g. ["MGW", "Roll", "ProT", "HelT"]
    model: str = "unknown"
    confidence: Confidence = Field(
        default_factory=lambda: Confidence(band=ConfidenceBand.UNKNOWN)
    )
    provenance: Provenance = Field(default_factory=Provenance)


# ---------------------------------------------------------------------------
# Injectable backend protocol
# ---------------------------------------------------------------------------


@runtime_checkable
class StructureBackend(Protocol):
    """Injectable backend wrapping real ESMFold/Boltz-2/Orca/DNAshapeR inference.

    Implementations handle transport, batching, GPU job submission, and coordinate-file
    upload; they return the heavy refs plus raw per-residue confidence. The service wraps
    them with model selection, provenance, confidence bands, low-confidence spans, Steps,
    evidence, and artifacts.
    """

    def predict_structure(self, request: StructureRequest) -> StructureResult: ...

    def predict_contacts(self, request: ContactMapRequest) -> ContactMapResult: ...

    def predict_dna_shape(self, request: DnaShapeRequest) -> DnaShapeResult: ...
