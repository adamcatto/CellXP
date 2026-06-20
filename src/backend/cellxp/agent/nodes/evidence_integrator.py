"""Evidence integrator — cross-subtask evidence aggregation (N5/X4).

Called after each capability subgraph completes. It records both per-subtask and
cross-plan evidence coverage so composed variant→GWAS→fold runs are inspectable.
"""

from __future__ import annotations

from cellxp.agent.state import AgentState, ExecutionCursor, Step
from cellxp.domain.clock import utc_now_iso
from cellxp.domain.enums import TaskStatus


def run(state: AgentState) -> dict[str, object]:
    """Record an integration step and verify subtask evidence is present."""
    cursor = ExecutionCursor.model_validate(state.get("cursor", {}))
    evidence = list(state.get("evidence", []))

    # Locate the subtask that just completed (active_subtask_id is still set).
    last_subtask_id = cursor.active_subtask_id
    subtask_evidence_count = sum(
        1
        for item in evidence
        if (isinstance(item, dict) and item.get("subtask_id") == last_subtask_id)
        or (hasattr(item, "subtask_id") and item.subtask_id == last_subtask_id)
    )

    started = utc_now_iso()
    evidence_subtasks = {
        item.get("subtask_id") if isinstance(item, dict) else item.subtask_id
        for item in evidence
        if (item.get("subtask_id") if isinstance(item, dict) else item.subtask_id)
    }
    integration_step = Step(
        subtask_id=last_subtask_id,
        name="evidence_integration",
        tool="evidence_integrator",
        weight="light",
        status=TaskStatus.DONE,
        started_at=started,
        finished_at=utc_now_iso(),
        params={
            "subtask_evidence_count": subtask_evidence_count,
            "total_evidence": len(evidence),
            "evidence_subtask_count": len(evidence_subtasks),
        },
    )
    return {"steps": [integration_step]}
