"""Conditional-edge routing for the supervisor graph."""

from __future__ import annotations

from cellxp.agent.state import AgentState, Clarification, ExecutionCursor, ReviewState, Subtask
from cellxp.domain.enums import ReviewDecision
from cellxp.domain.safety import RiskAssessment

_DESTINATIONS = {
    "variant_effect": "variant_effect_subgraph",
    "gwas": "gwas_subgraph",
    "crispr": "crispr_subgraph",
    "annotation": "annotation_subgraph",
    "binding": "binding_subgraph",
    "structure": "structure_subgraph",
    "origami": "origami_subgraph",
    "rag": "rag_subgraph",
    "visualization": "visualization_subgraph",
}


def route_after_risk(state: AgentState) -> str:
    risk = RiskAssessment.model_validate(state["risk"])
    return "report_generator" if risk.is_blocked else "entity_resolver"


def route_after_entities(state: AgentState) -> str:
    questions = [Clarification.model_validate(item) for item in state.get("clarifications", [])]
    if any(question.blocking and question.answer is None for question in questions):
        return "await_input"
    return "planner"


def has_pending_actionable_review(state: AgentState) -> bool:
    """Whether any actionable subject lacks a terminal review decision."""
    review = ReviewState.model_validate(state.get("review", {}))
    reviewed = {
        item.subject_ref
        for item in review.items
        if item.decision is not ReviewDecision.PENDING
    }
    actionable_artifacts = {
        item.id for item in state.get("artifacts", []) if getattr(item, "actionable", False)
    }
    actionable_subtasks = {
        item.id
        for raw in state.get("subtasks", [])
        if (item := Subtask.model_validate(raw)).is_actionable
    }
    return bool((actionable_artifacts | actionable_subtasks) - reviewed)


def route_task(state: AgentState) -> str:
    cursor = ExecutionCursor.model_validate(state.get("cursor", {}))
    if cursor.active_subtask_id is None:
        if has_pending_actionable_review(state):
            return "human_review_gate"
        return "critic"
    for raw_subtask in state.get("subtasks", []):
        subtask = Subtask.model_validate(raw_subtask)
        if subtask.id == cursor.active_subtask_id:
            return _DESTINATIONS.get(subtask.type.value, "critic")
    return "critic"
