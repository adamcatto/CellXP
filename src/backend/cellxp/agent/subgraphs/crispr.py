"""CRISPR capability subgraph (X5, FR-15)."""

from __future__ import annotations

from collections.abc import Callable

from cellxp.agent.state import AgentState, ExecutionCursor, NormalizedInputs, RunError, Step, Subtask
from cellxp.domain.clock import utc_now_iso
from cellxp.domain.enums import TaskStatus
from cellxp.services.base import ServiceOutcome
from cellxp.services.crispr import CrisprRequest, CrisprService, EditSpec

_Node = Callable[[AgentState], dict[str, object]]


def build_subgraph(*, crispr_service: CrisprService | None = None) -> _Node:
    service = crispr_service or CrisprService()

    def _run(state: AgentState) -> dict[str, object]:
        cursor = ExecutionCursor.model_validate(state.get("cursor", {}))
        subtasks = [Subtask.model_validate(x).model_copy(deep=True) for x in state.get("subtasks", [])]
        active = next((x for x in subtasks if x.id == cursor.active_subtask_id), None)
        if active is None:
            return {}
        inputs = NormalizedInputs.model_validate(state.get("normalized_inputs", {}))
        if not inputs.organism or not inputs.assembly:
            return _failure(active, subtasks, "CRISPR design requires organism and assembly")
        target = inputs.intervals[0] if inputs.intervals else (
            inputs.identifiers[0] if inputs.identifiers else None
        )
        if target is None:
            return _failure(active, subtasks, "CRISPR design requires a target interval or gene")

        raw_edit = active.inputs.get("edit_spec")
        edit_spec = EditSpec.model_validate(raw_edit) if raw_edit else None
        try:
            request = CrisprRequest(
                target=target, organism=inputs.organism, assembly=inputs.assembly,
                edit_type=active.inputs.get("edit_type", "knockout"), edit_spec=edit_spec,
                cas=active.inputs.get("cas"), pam=active.inputs.get("pam"),
                num_guides=active.inputs.get("num_guides", 10),
            )
        except ValueError as exc:
            return _failure(active, subtasks, str(exc), kind="InvalidEditSpec")

        result = service.design_guides(request)
        if result.outcome is ServiceOutcome.FAILURE:
            return _failure(
                active, subtasks, result.error.message if result.error else "CRISPR backend failed",
                prior_steps=result.steps, kind="CrisprServiceError",
            )
        active.status = TaskStatus.DONE
        active.result_ref = result.value.storage_ref if result.value else None
        return {
            "subtasks": subtasks, "steps": [*result.steps, _done(active.id)],
            "evidence": [x.model_copy(update={"subtask_id": active.id}) for x in result.evidence],
            "artifacts": [x.model_copy(update={"subtask_id": active.id}) for x in result.artifacts],
        }
    return _run


def _failure(active: Subtask, subtasks: list[Subtask], message: str, *,
             prior_steps: list[Step] | None = None, kind: str = "MissingInput") -> dict[str, object]:
    active.status = TaskStatus.FAILED
    return {
        "subtasks": subtasks,
        "steps": [*(prior_steps or []), Step(subtask_id=active.id, name="design_crispr_guides",
            status=TaskStatus.FAILED, error=message, finished_at=utc_now_iso())],
        "errors": [RunError(subtask_id=active.id, kind=kind, message=message)],
    }


def _done(subtask_id: str) -> Step:
    now = utc_now_iso()
    return Step(subtask_id=subtask_id, name="rank_candidate_guides", status=TaskStatus.DONE,
                started_at=now, finished_at=now)


run = build_subgraph()
