"""Typed contracts for model-guided inverse edit design (FR-18c)."""

from __future__ import annotations

from typing import Literal, Protocol, runtime_checkable

from pydantic import BaseModel, Field

from cellxp.domain.evidence import Confidence, Provenance
from cellxp.domain.models import GenomicInterval
from cellxp.services.crispr import EditSpec, OffTarget


class EffectTarget(BaseModel):
    readout: str
    direction: Literal["increase", "decrease", "abolish", "create", "shift"]
    magnitude: float | None = None


class ObjectiveWeights(BaseModel):
    on_target: float = Field(default=0.5, ge=0)
    off_target: float = Field(default=0.2, ge=0)
    collateral: float = Field(default=0.15, ge=0)
    feasibility: float = Field(default=0.15, ge=0)


class SearchBudget(BaseModel):
    max_candidates: int = Field(default=50, ge=1, le=1000)
    max_iterations: int = Field(default=3, ge=1, le=20)


class InverseDesignRequest(BaseModel):
    target_effect: EffectTarget
    locus: GenomicInterval | str
    organism: str
    assembly: str
    editor: str | None = None
    objective_weights: ObjectiveWeights = Field(default_factory=ObjectiveWeights)
    budget: SearchBudget = Field(default_factory=SearchBudget)


class CandidateProposal(BaseModel):
    edit: EditSpec
    editor: str


class CandidateAssessment(BaseModel):
    predicted_effect: float
    collateral_penalty: float = Field(ge=0.0, le=1.0)
    feasibility: float = Field(ge=0.0, le=1.0)
    off_targets: list[OffTarget] = Field(default_factory=list)
    off_target_penalty: float = Field(ge=0.0, le=1.0)
    confidence: Confidence
    provenance: Provenance = Field(default_factory=Provenance)


class EditCandidate(BaseModel):
    edit: EditSpec
    editor: str
    predicted_effect: float
    off_targets: list[OffTarget] = Field(default_factory=list)
    collateral_penalty: float
    feasibility: float
    score: float
    pareto_front: bool = False
    confidence: Confidence
    provenance: Provenance = Field(default_factory=Provenance)


class InverseDesignResult(BaseModel):
    candidates: list[EditCandidate] = Field(default_factory=list)
    iterations: int
    converged: bool
    target_gap: float | None = None
    storage_ref: str | None = None


@runtime_checkable
class InverseDesignBackend(Protocol):
    """Adapter combining proposal, forward-oracle, and CRISPR feasibility implementations."""

    def propose(self, request: InverseDesignRequest, iteration: int) -> list[CandidateProposal]: ...
    def assess(
        self, request: InverseDesignRequest, candidates: list[CandidateProposal]
    ) -> list[CandidateAssessment]: ...
