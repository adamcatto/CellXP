"""Model-guided inverse edit-design subgraph (X7, FR-18c)."""

from __future__ import annotations

from collections.abc import Callable

from cellxp.agent.state import (
    AgentState,
    ExecutionCursor,
    NormalizedInputs,
    RunError,
    Step,
    Subtask,
)
from cellxp.domain.clock import utc_now_iso
from cellxp.domain.enums import TaskStatus
from cellxp.services.base import ServiceOutcome
from cellxp.services.inverse_design import EffectTarget, InverseDesignRequest, InverseDesignService

_Node = Callable[[AgentState], dict[str, object]]


def build_subgraph(*, inverse_service: InverseDesignService | None = None) -> _Node:
    service = inverse_service or InverseDesignService()

    def _run(state: AgentState) -> dict[str, object]:
        cursor = ExecutionCursor.model_validate(state.get("cursor", {}))
        subtasks = [Subtask.model_validate(x).model_copy(deep=True) for x in state.get("subtasks", [])]
        active = next((x for x in subtasks if x.id == cursor.active_subtask_id), None)
        if active is None:
            return {}
        inputs = NormalizedInputs.model_validate(state.get("normalized_inputs", {}))
        locus = inputs.intervals[0] if inputs.intervals else (
            inputs.identifiers[0] if inputs.identifiers else None
        )
        target_raw = active.inputs.get("target_effect")
        if not inputs.organism or not inputs.assembly or locus is None or not target_raw:
            return _failure(active, subtasks, "inverse design requires target effect, locus, organism, and assembly")
        request = InverseDesignRequest(
            target_effect=EffectTarget.model_validate(target_raw), locus=locus,
            organism=inputs.organism, assembly=inputs.assembly, editor=active.inputs.get("editor"),
            objective_weights=active.inputs.get("objective_weights", {}),
            budget=active.inputs.get("search_budget", {}),
        )
        result = service.design(request)
        if result.outcome is ServiceOutcome.FAILURE:
            return _failure(active, subtasks, result.error.message if result.error else "inverse design failed",
                            prior_steps=result.steps, kind="InverseDesignError")
        active.status = TaskStatus.DONE
        active.result_ref = result.value.storage_ref if result.value else None
        return {
            "subtasks": subtasks, "steps": result.steps,
            "evidence": [x.model_copy(update={"subtask_id": active.id}) for x in result.evidence],
            "artifacts": [x.model_copy(update={"subtask_id": active.id}) for x in result.artifacts],
        }
    return _run


def _failure(active: Subtask, subtasks: list[Subtask], message: str, *,
             prior_steps: list[Step] | None = None, kind: str = "MissingInput") -> dict[str, object]:
    active.status = TaskStatus.FAILED
    return {
        "subtasks": subtasks,
        "steps": [*(prior_steps or []), Step(subtask_id=active.id, name="inverse_design",
            status=TaskStatus.FAILED, error=message, finished_at=utc_now_iso())],
        "errors": [RunError(subtask_id=active.id, kind=kind, message=message)],
    }


run = build_subgraph()
