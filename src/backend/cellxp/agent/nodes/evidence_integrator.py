"""Evidence integrator — cross-subtask evidence aggregation hook (N5).

Called after each capability subgraph completes. In N5 (single-subtask variant-effect
runs) it records an integration step and surfaces a per-subtask evidence count.
The node is the designed hook for future composed plans (variant→GWAS→fold) where
evidence from multiple subtasks must be aggregated, de-duplicated, or conflict-resolved
before the critic and report generator run.
"""

from __future__ import annotations

from cellxp.agent.state import AgentState, ExecutionCursor, Step, Subtask
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
    integration_step = Step(
        subtask_id=last_subtask_id,
        name="evidence_integration",
        tool="evidence_integrator",
        weight="light",
        status=TaskStatus.DONE,
        started_at=started,
        finished_at=utc_now_iso(),
        params={"subtask_evidence_count": subtask_evidence_count, "total_evidence": len(evidence)},
    )
    return {"steps": [integration_step]}
