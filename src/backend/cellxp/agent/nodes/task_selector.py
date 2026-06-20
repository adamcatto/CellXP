"""Deterministic dependency-aware subtask scheduler and loop hub."""

from __future__ import annotations

from cellxp.agent.state import AgentState, Budget, ExecutionCursor, RunError, Subtask
from cellxp.domain.enums import RunStatus, TaskStatus

_TERMINAL = {TaskStatus.DONE, TaskStatus.FAILED, TaskStatus.SKIPPED}


def _budget_exhausted(state: AgentState) -> bool:
    budget = Budget.model_validate(state.get("budget", {}))
    checks = (
        (budget.max_tokens, budget.spent.get("tokens", 0)),
        (budget.max_wallclock_s, budget.spent.get("wallclock_s", 0)),
        (budget.max_cost_usd, budget.spent.get("cost_usd", 0)),
    )
    return any(limit is not None and spent >= limit for limit, spent in checks)


def run(state: AgentState) -> dict[str, object]:
    subtasks = [
        Subtask.model_validate(item).model_copy(deep=True) for item in state.get("subtasks", [])
    ]
    by_id = {subtask.id: subtask for subtask in subtasks}
    completed = [subtask.id for subtask in subtasks if subtask.status is TaskStatus.DONE]
    errors: list[RunError] = []

    if _budget_exhausted(state):
        for subtask in subtasks:
            if subtask.status is TaskStatus.PENDING:
                subtask.status = TaskStatus.SKIPPED
        return {
            "subtasks": subtasks,
            "cursor": ExecutionCursor(completed=completed),
            "errors": [RunError(kind="BudgetExhausted", message="Run budget was exhausted.")],
        }

    for subtask in subtasks:
        if subtask.status is not TaskStatus.PENDING:
            continue
        dependencies = [by_id.get(dependency) for dependency in subtask.depends_on]
        if any(
            dep is None or dep.status in {TaskStatus.FAILED, TaskStatus.SKIPPED}
            for dep in dependencies
        ):
            subtask.status = TaskStatus.SKIPPED
            errors.append(
                RunError(
                    subtask_id=subtask.id,
                    kind="UnsatisfiedDependency",
                    message=f"Skipped {subtask.capability}: a dependency did not complete.",
                )
            )

    ready = next(
        (
            subtask
            for subtask in subtasks
            if subtask.status is TaskStatus.PENDING
            and all(
                by_id[dependency].status is TaskStatus.DONE for dependency in subtask.depends_on
            )
        ),
        None,
    )
    if ready is not None:
        ready.status = TaskStatus.RUNNING

    remaining = [subtask.id for subtask in subtasks if subtask.status not in _TERMINAL]
    update: dict[str, object] = {
        "subtasks": subtasks,
        "cursor": ExecutionCursor(
            active_subtask_id=ready.id if ready else None,
            completed=[subtask.id for subtask in subtasks if subtask.status is TaskStatus.DONE],
            remaining=remaining,
        ),
    }
    if errors:
        update["errors"] = errors
    if ready is None:
        from cellxp.agent.routing import has_pending_actionable_review

        routing_state = dict(state)
        routing_state["subtasks"] = subtasks
        if has_pending_actionable_review(routing_state):  # type: ignore[arg-type]
            update["status"] = RunStatus.AWAITING_REVIEW
    return update
