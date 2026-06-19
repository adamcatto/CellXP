"""Evidence, confidence, and provenance types.

Binding shapes from `state_schema.md` §9, semantics from
`documentation/explanation/evidence_and_confidence.md`, provenance rules from
`specs/data/provenance_model.md`. Every substantive claim links to >=1 `EvidenceItem`,
each carrying a `Confidence` (always a band, optionally a calibrated score) and a
`Provenance` sufficient to reproduce and audit it (`FR-23`/`FR-24`).
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, field_validator

from .enums import ConfidenceBand, SourceKind
from .ids import new_id


class Confidence(BaseModel):
    """How much to trust a claim (`evidence_and_confidence.md` §4).

    `band` is always present; `score` is an optional calibrated value in `[0, 1]`; `basis`
    states what the confidence rests on (model applicability, agreement, sample size).
    """

    band: ConfidenceBand
    score: float | None = None
    basis: str | None = None

    @field_validator("score")
    @classmethod
    def _score_in_unit_interval(cls, v: float | None) -> float | None:
        if v is not None and not (0.0 <= v <= 1.0):
            raise ValueError("confidence score must be in [0, 1]")
        return v


class Provenance(BaseModel):
    """What produced an evidence item, from what, with which tool version (`§4`).

    The core fields are the in-state shape (`state_schema.md` §9); the hash/seed/supersedes
    fields support content-addressing, caching, and corrections (`provenance_model.md`
    §6-§8, PROV-3/4/5) and default to absent so a minimal record stays valid.
    """

    tool: str | None = None
    tool_version: str | None = None  # "unknown" is recorded explicitly, never omitted (§4)
    params: dict[str, Any] = Field(default_factory=dict)
    inputs: dict[str, Any] = Field(default_factory=dict)  # normalized inputs (organism+assembly)
    citations: list[str] = Field(default_factory=list)  # DOIs/PMIDs/URLs/db accessions
    timestamp: str | None = None  # UTC ISO-8601
    input_hash: str | None = None
    output_hash: str | None = None
    output_ref: str | None = None
    nondeterministic: bool = False
    seed: int | None = None
    cache_hit: bool = False
    supersedes: str | None = None  # id of a corrected/retracted record (PROV-3)


class EvidenceItem(BaseModel):
    """A single attributable basis for a claim (`state_schema.md` §9)."""

    id: str = Field(default_factory=new_id)
    source: str  # model/tool/db name
    source_kind: SourceKind
    claim: str
    value: Any | None = None
    confidence: Confidence
    provenance: Provenance = Field(default_factory=Provenance)
    subtask_id: str | None = None
    step_id: str | None = None
