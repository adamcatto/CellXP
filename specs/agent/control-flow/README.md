# Agent Control Flow

How a run advances through the graph: lifecycle, transitions, pauses/resume, concurrency, and
replanning. These docs zoom into the dynamics that `graph_spec.md` and `routing_policy.md` describe
structurally; they own no new node behavior, only how nodes are sequenced.

Parent specs: `specs/agent/graph_spec.md`, `specs/agent/routing_policy.md`,
`specs/agent/state_schema.md`. Impl: `agent/graph.py`, `agent/routing.py`.

## Contents

| File | Covers |
|---|---|
| `control_flow_overview.md` | the end-to-end flow + the loop hub |
| `run_lifecycle.md` | `RunStatus`/`TaskStatus` states & transitions |
| `pause_and_resume.md` | `await_input` (clarification) and `await_review` (gate) pauses |
| `concurrency.md` | parallel subtasks, async heavy steps, safe reducers |
| `replanning_and_budget.md` | replanning triggers, loops, budget ceilings |
