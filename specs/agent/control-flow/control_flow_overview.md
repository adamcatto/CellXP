# Control Flow Overview

> Status: Draft v0.1. The end-to-end dynamics of a run. Structural definition: `graph_spec.md`.

## 1. Phases of a run

```
understand → plan → execute(loop) → [review?] → integrate → critique → report
```

1. **Understand** — `input_normalizer → intent_classifier → risk_classifier → entity_resolver`
   (may pause at `await_input`).
2. **Plan** — `planner` selects macro / atomic / composed and builds the subtask DAG.
3. **Execute (loop)** — `task_selector` dispatches ready subtasks to capability subgraphs and
   re-enters until the plan completes / fails / hits budget. This is the **loop hub**
   (`graph_spec.md` §3).
4. **Review** — actionable output pauses at `await_review` (`human_review_policy.md`).
5. **Integrate → Critique → Report** — `evidence_integrator → critic → report_generator → END`.

## 2. The loop hub

Unlike a one-shot switch, `task_selector` is re-entered after each subgraph so multi-subtask plans
(macros, composed/systems-level, inverse-design loops) run to completion. It chooses the next ready
subtask (deps satisfied), routes it, and exits to `critic` when none remain (`task_selector.md`).

## 3. Branch points

| At | Branch | Goes to |
|---|---|---|
| `risk_classifier` | `block` | refusal → `report_generator` |
| `entity_resolver` | blocking clarification | `await_input` (pause) |
| `task_selector` | ready subtask | `<capability>_subgraph` |
| `task_selector` | actionable output | `human_review_gate` → `await_review` |
| `task_selector` | plan done / budget | `critic` → `report_generator` |
| `critic` | fillable gap | replanning (`planner`) |

## 4. Always terminates at a report

Every terminating path ends at `report_generator`, which reports whatever evidence exists — including
explicit "insufficient evidence" / partial results (`NFR-6`, `mission.md` §5).

## 5. Related

`graph_spec.md` · `routing_policy.md` · `run_lifecycle.md` · `pause_and_resume.md` ·
`concurrency.md` · `replanning_and_budget.md`.
