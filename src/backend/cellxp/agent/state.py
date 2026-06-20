"""Agent state schema — the shared object that flows through the LangGraph agent.

Binding contract: `specs/agent/state_schema.md`. Substructures (this module's models) are
JSON-serializable Pydantic v2 models; the `AgentState` TypedDict that composes them, with
its concurrency reducers, is at the bottom of this file. When code and the spec diverge,
reconcile the spec first (ADR-0004).
"""

from __future__ import annotations

from operator import add
from typing import Any, Literal, TypedDict, TypeVar

from pydantic import BaseModel, Field
from typing_extensions import Annotated

from cellxp.domain.artifacts import ArtifactRef
from cellxp.domain.clock import utc_now_iso
from cellxp.domain.enums import (
    IntentType,
    PlanKind,
    ReviewDecision,
    ReviewGateStatus,
    RunStatus,
    SubtaskType,
    TaskStatus,
)
from cellxp.domain.evidence import Confidence, EvidenceItem
from cellxp.domain.ids import new_id
from cellxp.domain.models import GenomicInterval, Variant
from cellxp.domain.safety import RiskAssessment
from cellxp.domain.sequences import BiologicalSequence

# --- §5 conversation -------------------------------------------------------------------


class Message(BaseModel):
    id: str = Field(default_factory=new_id)
    role: Literal["user", "assistant", "system", "tool"]
    content: str
    created_at: str = Field(default_factory=utc_now_iso)
    artifact_ids: list[str] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)
    step_id: str | None = None


# --- §7 inputs & entities --------------------------------------------------------------


class RawInput(BaseModel):
    id: str = Field(default_factory=new_id)
    kind: Literal["text", "file", "sequence", "variant", "interval", "identifier"]
    value: str | None = None
    file_ref: str | None = None  # object-store key for uploads
    mime: str | None = None


class NormalizedInputs(BaseModel):
    organism: str | None = None  # required before coordinate ops (FR-11)
    assembly: str | None = None
    sequences: list[BiologicalSequence] = Field(default_factory=list)
    variants: list[Variant] = Field(default_factory=list)
    intervals: list[GenomicInterval] = Field(default_factory=list)
    identifiers: list[str] = Field(default_factory=list)  # rsIDs, gene symbols, accessions
    warnings: list[str] = Field(default_factory=list)


class Entity(BaseModel):
    id: str = Field(default_factory=new_id)
    type: Literal[
        "gene", "variant", "interval", "protein", "metabolite",
        "transcript", "regulatory_element", "organism", "pathway",
    ]
    label: str
    resolved: bool = False  # False -> needs clarification
    organism: str | None = None
    assembly: str | None = None
    refs: dict[str, str] = Field(default_factory=dict)  # cross-DB IDs (Ensembl, UniProt, …)
    ambiguity: list[str] = Field(default_factory=list)  # candidate resolutions if unresolved


class ClarificationOption(BaseModel):
    id: str = Field(default_factory=new_id)
    label: str
    value: str | None = None
    is_recommended: bool = False


class ClarificationAnswer(BaseModel):
    selected_option_ids: list[str] = Field(default_factory=list)
    freeform: str | None = None  # "yes, and …" / "Other" addition
    answered_at: str | None = None


class Clarification(BaseModel):
    id: str = Field(default_factory=new_id)
    question: str
    options: list[ClarificationOption] = Field(default_factory=list)
    allow_multiple: bool = False
    allow_freeform: bool = True
    blocking: bool = True
    answer: ClarificationAnswer | None = None


# --- §6 plan, subtasks & cursor --------------------------------------------------------


class Plan(BaseModel):
    id: str = Field(default_factory=new_id)
    kind: PlanKind
    macro_id: str | None = None  # set when kind == macro
    rationale: str | None = None
    created_by: Literal["router", "planner", "macro", "user"]
    revision: int = 0


class Subtask(BaseModel):
    id: str = Field(default_factory=new_id)
    type: SubtaskType
    capability: str  # FR ref / capability key
    inputs: dict[str, Any] = Field(default_factory=dict)
    depends_on: list[str] = Field(default_factory=list)  # subtask IDs (DAG)
    status: TaskStatus = TaskStatus.PENDING
    result_ref: str | None = None
    is_actionable: bool = False  # triggers review gate (§12)


class ExecutionCursor(BaseModel):
    active_subtask_id: str | None = None
    completed: list[str] = Field(default_factory=list)
    remaining: list[str] = Field(default_factory=list)


# --- §8 steps --------------------------------------------------------------------------


class Step(BaseModel):
    id: str = Field(default_factory=new_id)
    subtask_id: str | None = None
    name: str  # e.g. "extract_coordinates", "call_alphagenome"
    weight: Literal["light", "heavy"] = "light"  # heavy -> async job
    tool: str | None = None
    tool_version: str | None = None
    params: dict[str, Any] = Field(default_factory=dict)
    input_ref: dict[str, Any] = Field(default_factory=dict)
    output_ref: str | None = None
    job_id: str | None = None  # for async heavy steps
    status: TaskStatus = TaskStatus.PENDING
    started_at: str | None = None
    finished_at: str | None = None
    error: str | None = None


# --- §11 report ------------------------------------------------------------------------


class Report(BaseModel):
    markdown: str = ""
    citation_map: dict[str, str] = Field(default_factory=dict)  # citation marker -> evidence_id
    artifact_ids: list[str] = Field(default_factory=list)
    confidence_summary: Confidence | None = None
    limitations: list[str] = Field(default_factory=list)
    suggested_followups: list[str] = Field(default_factory=list)


# --- §12 human-review state ------------------------------------------------------------


class ReviewItem(BaseModel):
    id: str = Field(default_factory=new_id)
    subject_ref: str  # artifact/subtask under review
    reason: str  # why it's actionable
    risks: list[str] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)
    decision: ReviewDecision = ReviewDecision.PENDING
    note: str | None = None


class ReviewState(BaseModel):
    required: bool = False  # set when any actionable output is produced
    status: ReviewGateStatus = ReviewGateStatus.NOT_REQUIRED
    items: list[ReviewItem] = Field(default_factory=list)
    decided_at: str | None = None


# --- §13 errors ------------------------------------------------------------------------


class RunError(BaseModel):
    id: str = Field(default_factory=new_id)
    subtask_id: str | None = None
    step_id: str | None = None
    kind: str  # see domain/errors.py
    message: str
    recoverable: bool = True  # if True, run continues (partial results, NFR-6)
    at: str = Field(default_factory=utc_now_iso)


# --- §15 budget ------------------------------------------------------------------------


class Budget(BaseModel):
    max_tokens: int | None = None
    max_wallclock_s: int | None = None
    max_cost_usd: float | None = None
    spent: dict[str, float] = Field(default_factory=dict)


# --- §16 reducers ----------------------------------------------------------------------

_HasId = TypeVar("_HasId")


def merge_by_id(left: list[_HasId], right: list[_HasId]) -> list[_HasId]:
    """Merge-by-id reducer (`state_schema.md` §16): items with the same `.id` are replaced,
    new items appended. Used for `entities`/`clarifications`, which resolvers/UI update
    incrementally rather than purely appending.
    """
    if not left:
        return right
    if not right:
        return left
    index = {item.id: i for i, item in enumerate(left)}  # type: ignore[attr-defined]
    merged = list(left)
    for item in right:
        key = item.id  # type: ignore[attr-defined]
        if key in index:
            merged[index[key]] = item
        else:
            index[key] = len(merged)
            merged.append(item)
    return merged


# --- §4 target AgentState --------------------------------------------------------------


class AgentState(TypedDict, total=False):
    """The shared working memory passed between graph nodes (`state_schema.md` §4).

    Append fields use `Annotated[list, add]`; merge-by-id fields use `merge_by_id`;
    everything else is last-write-wins (single owner node). Parallel nodes MUST only write
    append/merge-by-id fields to avoid clobbering (§16).
    """

    # identity & meta
    schema_version: str
    run_id: str
    created_at: str
    session_type: str
    review_posture: Literal["standard", "strict"]

    # conversation
    messages: Annotated[list[Message], add]
    user_query: str

    # inputs (raw -> normalized)
    raw_inputs: list[RawInput]
    normalized_inputs: NormalizedInputs

    # understanding
    intent: IntentType
    risk: RiskAssessment
    entities: Annotated[list[Entity], merge_by_id]
    clarifications: Annotated[list[Clarification], merge_by_id]

    # plan & execution
    plan: Plan
    subtasks: list[Subtask]
    steps: Annotated[list[Step], add]
    cursor: ExecutionCursor

    # outputs
    evidence: Annotated[list[EvidenceItem], add]
    artifacts: Annotated[list[ArtifactRef], add]
    final_report: Report

    # control
    review: ReviewState
    errors: Annotated[list[RunError], add]
    status: RunStatus
    budget: Budget
    target_effect: dict[str, Any]


__all__ = [
    "Message", "RawInput", "NormalizedInputs", "Entity", "ClarificationOption",
    "ClarificationAnswer", "Clarification", "Plan", "Subtask", "ExecutionCursor", "Step",
    "Report", "ReviewItem", "ReviewState", "RunError", "Budget", "AgentState",
    "ArtifactRef", "EvidenceItem", "RiskAssessment", "merge_by_id",
]
