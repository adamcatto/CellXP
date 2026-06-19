# task_selector Node

> Status: Draft v0.1. Node 6 — the **loop hub**. Parent: `graph_spec.md` §3/§7, `routing_policy.md`
> §8. Impl: `agent/nodes/task_selector.py`, `agent/routing.py`. Deterministic.

## Purpose

Drive execution: pick the next ready subtask and route it to the right capability subgraph, looping
until the plan completes, fails, or hits budget.

## Reads → Writes

- **Reads:** `subtasks`, `cursor`, `plan`, `budget`.
- **Writes:** `cursor` (last-write-wins); returns the routing destination.

## Behavior

1. Select the next **ready** subtask (all `depends_on` complete, status `pending`).
2. Route via `route_task` to the matching `<capability>_subgraph` (`graph_spec.md` §5).
3. If the active subtask is `is_actionable` and has produced output → route to `human_review_gate`.
4. If no ready subtasks remain (or `budget` exhausted) → route to `critic` → `report_generator`.
5. Update `cursor` (active/completed/remaining); may mark independent ready subtasks for concurrent
   dispatch (`control-flow/concurrency.md`).

## Errors / edge cases

- All remaining subtasks blocked (unsatisfiable deps) → mark skipped, append error, proceed to report
  with partial results (`NFR-6`).
- Budget hit mid-plan → stop dispatch, report what exists.

## Open questions

- Concurrency degree / scheduling policy.
- Whether selection itself can request replanning vs deferring to `critic`.

## Related

`routing_policy.md` §8 · `graph_spec.md` §5/§9 · `control-flow/concurrency.md` · `state_schema.md` §6.
