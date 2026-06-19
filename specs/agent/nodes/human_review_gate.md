# human_review_gate Node

> Status: Draft v0.1. Node 8 — the actionable-biology gate. Parent: `graph_spec.md` §8,
> `human_review_policy.md`, ADR-0005. Impl: `agent/nodes/human_review_gate.py`,
> `domain/safety.py`. Pause node.

## Purpose

Enforce human-in-the-loop review for actionable outputs: pause the run, present candidates +
evidence + risks, and gate progression on an explicit decision.

## Reads → Writes

- **Reads:** `subtasks` (`is_actionable`), `artifacts` (`actionable`), `evidence`, `risk`.
- **Writes:** `review` (`ReviewState`/`ReviewItem`s), `status=awaiting_review`.

## Behavior

1. Collect actionable artifacts into `ReviewItem`s (subject, rationale, risks, evidence ids)
   (`state_schema.md` §12).
2. Set `review.required=true`, `status=awaiting_review` → run pauses (`control-flow/pause_and_resume.md`).
3. On resume with decisions: `approved` → output becomes recommendation, continue; `rejected` →
   withhold; `changes_requested` → trigger replanning (`routing_policy.md` §9).
4. Record decisions + notes + timestamps to `review` and the audit log (`specs/data/audit_log.md`).

## Invariants

- MUST NOT present an actionable output as recommended, nor perform a gated side effect, while its
  `ReviewItem.decision == pending`.
- Cannot override a safety `block` (`safety_model.md` §7).
- Enforcement = 100% (`success_metrics.md` D5; `tests/integration/test_crispr_gate.py`).

## Open questions

- One aggregate gate vs per-subtask interrupts.
- Reviewer roles/permissions; pending-review expiry.

## Related

`human_review_policy.md` · `safety_model.md` · `control-flow/pause_and_resume.md` ·
`specs/interface/chat_interface.md`.
