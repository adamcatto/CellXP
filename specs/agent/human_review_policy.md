# Human Review Policy

> Status: Draft v0.1. Defines the human-in-the-loop gate for **actionable biology** (ADR-0005,
> `FR-25/26`): what counts as actionable, how the gate pauses and resumes the run, what the reviewer
> sees and decides, and how decisions are recorded. Consumes `ReviewState`/`ReviewItem`
> (`state_schema.md` §12) and the `await_review` pause (`graph_spec.md` §8). Implementation:
> `agent/nodes/human_review_gate.py`, `domain/safety.py`.

## 1. Principle

CellXP is a copilot, not an autopilot. The agent reasons and *proposes* freely, but it
never silently advances from analysis to a **recommended actionable output** or commits a
consequential side effect, unless explicitly directed to (with additional confirmation) during a run. Such outputs are presented as **candidates with rationale** and require
explicit human acknowledgement before being framed as recommendations or written/committed
(`mission.md` §3).

## 2. What is "actionable" (gate triggers)

A subtask/artifact is **actionable** when it proposes a physical intervention or a consequential side
effect, including:
- **Genome edits** — CRISPR guides, base/prime edits, knockouts/knock-ins (`crispr`, `FR-15`).
- **Inverse edit designs** — edits proposed to achieve a target effect (`FR-18c`).
- **Strain/pathway engineering** interventions (`FR-18d`, `task_patterns.md` §6).
- **Protein/sequence designs** — designed proteins, binders, primers (`FR-18a`).
- **DNA origami / nanostructure** designs (`FR-19`).
- **Consequential side effects** — writing/committing files or external mutations beyond ephemeral
  artifacts (`mission.md` §3).

Producing subtasks set `is_actionable=true` (`routing_policy.md` §7); `tool_use_policy.md` §10 marks
actionable/generative tools. `risk=restrict` (`safety_model.md`) also forces the gate.

Analysis-only outputs (interpretation, lookups, predictions, visualizations) are **not** gated.

## 3. Gate flow

```
actionable artifact produced
   → human_review_gate sets review.required = true, status = "pending"
   → run enters await_review (status = awaiting_review)         [graph_spec §8]
   → reviewer sees ReviewItem(s): proposal + evidence + risks
   → decision: approve | reject | request changes
        approve         → output becomes a recommendation; run continues / completes
        reject          → output withheld; run records rejection; may stop or replan
        request changes → planner revises (routing_policy §9) within budget
```

The graph MUST NOT emit an actionable output as a *recommendation*, nor perform a gated side effect,
while `ReviewItem.decision == pending`.

## 4. What the reviewer is shown (per `ReviewItem`)

- **Proposal** — the concrete candidate (e.g. guide table rows, edited sequence, design file) with
  the `subject_ref` artifact.
- **Rationale** — why the agent proposes it (linked subtask/plan rationale).
- **Evidence** — supporting `EvidenceItem`s with confidence (`evidence_integration.md`).
- **Risks** — off-target/collateral profile, feasibility caveats, safety notes, limitations.
- **Confidence & assumptions** — explicit (`evidence_and_confidence.md`).

Presentation contract for the UI: `specs/interface/chat_interface.md` (review prompt) and
`artifact_model.md` (gated artifact rendering).

## 5. Decisions & recording

```python
decision ∈ {approved, rejected}      # per ReviewItem
status   ∈ {pending, approved, rejected, changes_requested}   # aggregate ReviewState
```

- Each decision records reviewer note + timestamp into `ReviewState` and the audit log
  (`specs/data/audit_log.md`).
- A run with any unapproved actionable item MUST NOT present that item as recommended.
- Decisions are part of the reproducible trace (`FR-24`): who approved what, when, on what evidence.

## 6. Granularity

- One `human_review_gate` node aggregates all pending `ReviewItem`s for a run (current design,
  `graph_spec.md` §11), so a multi-edit design is reviewed coherently.
- Each distinct actionable artifact gets its own `ReviewItem` so reviewers can approve/reject
  selectively (e.g. accept guide #2, reject #5).

## 7. Interaction with safety

The review gate is **downstream** of the safety risk gate, not a replacement:
- `risk=block` → refused earlier; never reaches review (`safety_model.md`, `FR-33/34`).
- `risk=restrict` → allowed but **always** review-gated.
- `risk=allow` + actionable → review-gated by actionability.
Approval at the review gate does NOT override a safety block.

## 8. Non-bypass guarantees

- The gate cannot be skipped by composed/macro plans: actionability is a property of the producing
  subtask, enforced in `task_selector` routing (`graph_spec.md` §6.4).
- Test coverage: `tests/integration/test_crispr_gate.py` (and analogous per actionable capability)
  asserts no recommended actionable output escapes without approval. Metric:
  review-gate enforcement = 100% (`success_metrics.md` D5).

## 9. Resume semantics

`await_review` is a durable, checkpointed pause (`graph_spec.md` §8, `specs/data/*`). The API exposes
a submit-review-decision endpoint (`api_contracts.md`) that re-enters the gate node with the
decisions; the run then continues, replans, or completes per §3.

## 10. Open questions

- Roles/permissions: who may approve (any user vs designated reviewer/PI persona P4)? Org policy
  config?
- Auto-expiry of pending reviews; notifications.
- Per-capability risk thresholds that escalate from "review" to "block".

## 11. Related specs

`state_schema.md` §12 · `graph_spec.md` §8 · `routing_policy.md` · `tool_use_policy.md` ·
`safety_model.md` · `specs/data/audit_log.md` · `specs/interface/chat_interface.md` ·
`success_metrics.md` · ADR-0005.
