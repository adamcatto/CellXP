# Pause & Resume (human-in-the-loop)

> Status: Draft v0.1. The two durable pauses and how runs resume. Mechanism: LangGraph interrupts +
> state checkpointing (`graph_spec.md` §8).

## 1. Two pause points

| Pause | Trigger | Status | Set by | Resumed by |
|---|---|---|---|---|
| `await_input` | open **blocking** `Clarification` | `awaiting_input` | `entity_resolver` (or any node) | user answer |
| `await_review` | pending `ReviewState` (actionable output) | `awaiting_review` | `human_review_gate` | review decision |

## 2. Durability

State is checkpointed at the pause and persisted (`specs/data/*`), keyed by `run_id`. A paused run
survives process restarts and can be resumed minutes or days later.

## 3. await_input (clarification)

- `entity_resolver` (or planner) emits a blocking `Clarification` when a consequential parameter is
  missing/ambiguous (organism, assembly, edit intent, etc.; `routing_policy.md` §4, `FR-7`).
- The run pauses; the UI shows the question(s) (batched, targeted).
- Resume re-enters the emitting node with `Clarification.answer` filled; dependent subtasks unblock.

## 4. await_review (gate)

- `human_review_gate` builds `ReviewItem`s and pauses (`human_review_policy.md`).
- Resume submits per-item decisions: `approved` → continue; `rejected` → withhold; `changes_requested`
  → replanning (`replanning_and_budget.md`).
- Until approved, no actionable output is presented as a recommendation and no gated side effect runs.

## 5. API surface

The API exposes resume endpoints (answer-clarification, submit-review-decision) that re-enter the
graph at the paused node (`api_contracts.md`); the corresponding `clarification.requested` /
`review.requested` events tell the client to prompt. The interactive presentation of these prompts —
option cards, recommended option, multi-select, and the "yes, and …" free-text affordance — is
specified in `specs/interface/streaming_protocol.md` §7–§8.

## 6. Related

`graph_spec.md` §8 · `human_review_policy.md` · `routing_policy.md` §4 · `run_lifecycle.md` ·
`api_contracts.md` · `state_schema.md` §12.
