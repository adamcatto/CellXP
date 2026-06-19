# planner Node

> Status: Draft v0.1. Node 5. Parent: `graph_spec.md` §4, `routing_policy.md` §5–§7,
> `task_patterns.md`. Impl: `agent/nodes/planner.py`, prompt `agent/prompts/planner.md`. LLM-backed.

## Purpose

Decide the plan kind and build the subtask DAG: refuse / clarify / **macro** / **atomic** /
**composed** (task taxonomy, `task_patterns.md` §0).

## Reads → Writes

- **Reads:** `intent`, `risk`, `entities`, `normalized_inputs`, (macro registry).
- **Writes:** `plan` (last-write-wins), `subtasks` (the DAG), may raise `plan.revision`.

## Behavior

1. Apply plan-selection priority (`routing_policy.md` §5): refuse → clarify → macro-match → atomic →
   composed.
2. **Macro:** if a registered macro's triggers match and parameters resolve, set `plan.kind="macro"`,
   `macro_id`, and expand its pre-baked subtasks.
3. **Atomic:** single capability → one `Subtask` with a fixed internal pipeline.
4. **Composed:** decompose into a `Subtask` DAG with `depends_on`; mark `is_actionable` subtasks;
   instantiate systems-level recipes (`task_patterns.md` §2–§6); express inverse-design loops as
   re-addable subtasks bounded by `budget`.
5. Record a brief `rationale`.

## Errors / edge cases

- Macro partially parameterizable → fall back to clarify/composed.
- Replanning on re-entry (`routing_policy.md` §9): raise `revision`, respect revision cap.

## Prompt

`agent/prompts/planner.md` (+ `supervisor.md` context).

## Open questions

- LLM-built DAG vs templated skeletons per intent.
- Convergence/stop criteria for looped composed plans.

## Related

`routing_policy.md` · `task_patterns.md` · `task_selector.md` · `state_schema.md` §6.
