"""Human-review gate node (FR-25, FR-26, human_review_policy.md §5).

Any actionable output (is_actionable=True on an artifact or subtask) must pass this gate
before being released to the user. The gate:

1. Audits review.requested for each pending item (AL-1).
2. Interrupts (LangGraph durable pause) to wait for a reviewer decision.
3. On resume, applies the decision and audits review.decided; if approved, also audits
   actionable.emitted for each released artifact (AL-1, AL-6).

The node is provided as a factory (make_human_review_gate) so an AuditRepository can be
injected at graph-build time. The module-level `run` is the no-audit default.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from langgraph.types import interrupt

from cellxp.agent.state import AgentState, ReviewItem, ReviewState, Subtask
from cellxp.domain.audit import AGENT_ACTOR, AuditEventType
from cellxp.domain.clock import utc_now_iso
from cellxp.domain.enums import ReviewDecision, ReviewGateStatus, RunStatus

if TYPE_CHECKING:
    from cellxp.storage.audit_repository import AuditRepository


def make_human_review_gate(
    audit_repo: AuditRepository | None = None,
) -> Callable[[AgentState], dict[str, object]]:
    """Return a human_review_gate node with an optionally injected AuditRepository."""

    def _run(state: AgentState) -> dict[str, object]:
        run_id: str | None = state.get("run_id")
        artifacts = state.get("artifacts", [])
        existing_review = ReviewState.model_validate(state.get("review", {}))

        # Collect actionable artifacts that haven't been reviewed yet.
        reviewed_subjects = {item.subject_ref for item in existing_review.items}
        pending_artifacts = [
            a for a in artifacts
            if getattr(a, "actionable", False) and a.id not in reviewed_subjects
        ]
        pending_subtasks = [
            subtask
            for raw in state.get("subtasks", [])
            if (subtask := Subtask.model_validate(raw)).is_actionable
            and subtask.id not in reviewed_subjects
            and not any(getattr(artifact, "subtask_id", None) == subtask.id for artifact in artifacts)
        ]

        if not pending_artifacts and not pending_subtasks:
            # Nothing actionable; gate is a no-op.
            return {"review": existing_review}

        # Build review items for each pending artifact.
        new_items: list[ReviewItem] = list(existing_review.items)
        for artifact in pending_artifacts:
            item = ReviewItem(
                id=f"review-{artifact.id}",
                subject_ref=artifact.id,
                reason="Actionable output requires human review before release.",
                risks=[],
                evidence_ids=[],
                decision=ReviewDecision.PENDING,
            )
            new_items.append(item)

            if audit_repo is not None:
                audit_repo.append(
                    event_type=AuditEventType.REVIEW_REQUESTED,
                    actor=AGENT_ACTOR,
                    run_id=run_id,
                    subject_ref=artifact.id,
                    payload={
                        "review_item_id": item.id,
                        "reason": item.reason,
                        "artifact_type": getattr(artifact, "type", None),
                    },
                )

        for subtask in pending_subtasks:
            item = ReviewItem(
                id=f"review-{subtask.id}",
                subject_ref=subtask.id,
                reason=f"Actionable {subtask.capability} subtask requires human review.",
                evidence_ids=[
                    evidence.id
                    for evidence in state.get("evidence", [])
                    if evidence.subtask_id == subtask.id
                ],
                decision=ReviewDecision.PENDING,
            )
            new_items.append(item)
            if audit_repo is not None:
                audit_repo.append(
                    event_type=AuditEventType.REVIEW_REQUESTED,
                    actor=AGENT_ACTOR,
                    run_id=run_id,
                    subject_ref=subtask.id,
                    payload={
                        "review_item_id": item.id,
                        "reason": item.reason,
                        "capability": subtask.capability,
                    },
                )

        review = ReviewState(
            required=True,
            status=ReviewGateStatus.PENDING,
            items=new_items,
        )

        # Pause; the reviewer's decision dict is returned when the run resumes.
        raw_decision: Any = interrupt(review.model_dump(mode="json"))

        # Apply the decision — raw_decision is a dict with {item_id: decision_str, note?: str}.
        decision_map: dict[str, str] = {}
        note: str | None = None
        if isinstance(raw_decision, dict):
            decision_map = {k: v for k, v in raw_decision.items() if k != "note"}
            note = raw_decision.get("note")

        decided_at = utc_now_iso()
        final_items: list[ReviewItem] = []
        for item in review.items:
            raw = decision_map.get(item.id)
            try:
                decision = ReviewDecision(raw) if raw else ReviewDecision.PENDING
            except ValueError:
                decision = ReviewDecision.PENDING

            updated = item.model_copy(update={"decision": decision, "note": note})
            final_items.append(updated)

            if audit_repo is not None and decision is not ReviewDecision.PENDING:
                audit_repo.append(
                    event_type=AuditEventType.REVIEW_DECIDED,
                    actor=AGENT_ACTOR,
                    run_id=run_id,
                    subject_ref=item.subject_ref,
                    payload={
                        "review_item_id": item.id,
                        "decision": decision.value,
                        "note": note,
                    },
                )
                if decision is ReviewDecision.APPROVED and audit_repo is not None:
                    audit_repo.append(
                        event_type=AuditEventType.ACTIONABLE_EMITTED,
                        actor=AGENT_ACTOR,
                        run_id=run_id,
                        subject_ref=item.subject_ref,
                        payload={
                            "artifact_id": item.subject_ref,
                            "approving_review_item_id": item.id,
                        },
                    )

        all_decided = all(i.decision is not ReviewDecision.PENDING for i in final_items)
        any_approved = any(i.decision is ReviewDecision.APPROVED for i in final_items)
        gate_status = (
            ReviewGateStatus.APPROVED if any_approved and all_decided
            else ReviewGateStatus.REJECTED if all_decided
            else ReviewGateStatus.PENDING
        )

        final_review = ReviewState(
            required=True,
            status=gate_status,
            items=final_items,
            decided_at=decided_at if all_decided else None,
        )
        return {"review": final_review, "status": RunStatus.RUNNING}

    return _run


# Default node function — no audit writes.
run = make_human_review_gate()
