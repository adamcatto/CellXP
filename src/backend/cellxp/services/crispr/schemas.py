"""Typed CRISPR requests, results, and injectable backend protocol (FR-15)."""

from __future__ import annotations

from typing import Literal, Protocol, runtime_checkable

from pydantic import BaseModel, Field, model_validator

from cellxp.domain.evidence import Confidence, Provenance
from cellxp.domain.models import GenomicInterval


class EditSpec(BaseModel):
    position: int = Field(ge=0)
    ref: str
    alt: str


class OffTarget(BaseModel):
    locus: GenomicInterval
    mismatches: int = Field(ge=0)
    cfd_score: float = Field(ge=0.0, le=1.0)


class Guide(BaseModel):
    spacer: str = Field(min_length=15, max_length=30)
    pam: str
    strand: Literal["+", "-"]
    cut_site: int = Field(ge=0)
    on_target_score: float = Field(ge=0.0, le=1.0)
    off_targets: list[OffTarget] = Field(default_factory=list)
    specificity_score: float = Field(ge=0.0, le=1.0)
    feasibility_notes: list[str] = Field(default_factory=list)
    confidence: Confidence
    provenance: Provenance = Field(default_factory=Provenance)


class CrisprRequest(BaseModel):
    target: GenomicInterval | str
    organism: str
    assembly: str
    edit_type: Literal["knockout", "knockin", "base_edit", "prime_edit", "interference"]
    edit_spec: EditSpec | None = None
    cas: str | None = None
    pam: str | None = None
    num_guides: int = Field(default=10, ge=1, le=100)

    @model_validator(mode="after")
    def _require_edit_spec(self) -> "CrisprRequest":
        if self.edit_type in {"base_edit", "prime_edit"} and self.edit_spec is None:
            raise ValueError(f"{self.edit_type} requires edit_spec")
        return self


class CrisprResult(BaseModel):
    guides: list[Guide] = Field(default_factory=list)
    editing_system: str
    rationale: str
    storage_ref: str | None = None
    off_target_storage_ref: str | None = None


class OffTargetRequest(BaseModel):
    guides: list[str] = Field(min_length=1)
    organism: str
    assembly: str
    max_mismatches: int = Field(default=4, ge=0, le=8)


class OffTargetResult(BaseModel):
    hits: dict[str, list[OffTarget]] = Field(default_factory=dict)
    storage_ref: str | None = None


class GuideScoringRequest(BaseModel):
    guides: list[str] = Field(min_length=1)
    organism: str
    assembly: str
    model: str = "auto"
    genomic_contexts: dict[str, str] | None = None


class GuideScoringResult(BaseModel):
    scores: dict[str, float]


class EditOutcomeRequest(BaseModel):
    guides: list[str] = Field(min_length=1)
    edit_spec: EditSpec
    organism: str
    assembly: str
    editor: str


class EditOutcomeResult(BaseModel):
    efficiencies: dict[str, float]
    outcome_model: str


@runtime_checkable
class CrisprBackend(Protocol):
    def design_guides(self, request: CrisprRequest) -> CrisprResult: ...
    def enumerate_off_targets(self, request: OffTargetRequest) -> OffTargetResult: ...
    def score_on_target(self, request: GuideScoringRequest) -> GuideScoringResult: ...
    def predict_edit_outcomes(self, request: EditOutcomeRequest) -> EditOutcomeResult: ...
