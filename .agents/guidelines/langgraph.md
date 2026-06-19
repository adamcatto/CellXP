# LangGraph Implementation Guidelines

How we build the agent graph. Specs: `specs/agent/graph_spec.md`, `state_schema.md`,
`control-flow/*`. Code: `src/backend/cellxp/agent/`.

## When to reach for LangGraph

Use LangGraph for the **L1 supervisor** and **capability subgraphs** — anywhere we need explicit
control of ordering (safety-first), durable pauses (review gate), and full state/provenance. For a
lighter single-capability agent, `langchain.create_agent` may suffice (`langchain.md`); for deep
context-heavy subtasks, use `deepagents` (`deepagents.md`).

## State

- One `TypedDict` `AgentState` (`agent/state.py`) is the single source of truth (`state_schema.md`).
- Use **reducers** deliberately: `Annotated[list[X], add]` for append fields
  (`messages`, `steps`, `evidence`, `artifacts`, `errors`); custom merge-by-id for `entities`/
  `clarifications`; plain last-write-wins for single-owner fields (`plan`, `cursor`, `status`, …).
- **Concurrency rule:** any node that can run in parallel may write **only** append/merge-by-id
  fields. Writing a last-write-wins field from a parallel branch is a bug (`state_schema.md` §16).
- Keep state JSON-serializable (Pydantic v2 models / TypedDicts) and carry `schema_version`.

## Nodes

- A node is `(state) -> partial_state_update` (return only changed keys; never mutate in place).
- Keep nodes single-purpose and named exactly as in `specs/agent/nodes/*`.
- Deterministic work (parsing, coords, dispatch, scoring) is plain Python; LLM work goes through the
  model abstraction (`langchain.md`) and returns **schema-validated** output.
- Record every tool/model/data call as a `Step` (tool + version + params + IO refs) for provenance.

## Edges & routing

- Linear edges for the preamble; `add_conditional_edges` for routing.
- `task_selector` is a **loop hub**: it re-enters after each subgraph until the plan completes/fails/
  hits budget — don't model it as a one-shot switch (`graph_spec.md` §3, `control-flow/control_flow_overview.md`).
- Routing logic lives in `agent/routing.py` (`route_task`) and follows `routing_policy.md`. Keep the
  destination set in sync with the subgraph registry.

## Subgraphs

- Each capability is a compiled subgraph under `agent/subgraphs/` with the uniform contract: in =
  `Subtask` (+ inputs), out = appended `evidence`/`artifacts` + `Subtask.status`
  (`capability-subgraphs/README.md`).
- Adding a capability must not change the top-level spine (`NFR-11`, ADR-0003): add a subgraph,
  register its service, declare selection metadata, make it reachable from `route_task`.

## Pauses, checkpointing, resume

- Use **interrupts + a checkpointer** for the two pauses: `await_input` (blocking `Clarification`) and
  `await_review` (`ReviewState`). Set `status` accordingly (`control-flow/pause_and_resume.md`).
- Use a **durable checkpointer** (Postgres/Redis) so paused runs survive restarts and resume days
  later. `run_id` (and `session_id`, `session_types.md`) are the keys.
- Resume by re-entering the paused node with the user's answer/decision filled in state.

## Streaming

- Stream state deltas as typed events (`state_schema.md` §17, `specs/interface/streaming_protocol.md`).
- Use LangGraph streaming modes to emit token deltas (`message`/`report`), reasoning, and state
  updates. Reasoning/activity events are best-effort; state-backed events are replayable.

## Async & heavy work

- Heavy steps (GPU models, genome-wide scans) dispatch to job workers (Redis queue); the node awaits
  the job, emitting `activity.update` liveness, without blocking the loop
  (`control-flow/concurrency.md`, `architecture_overview.md` §7).
- Prefer async node functions for IO-bound fan-out.

## Testing

- Unit-test nodes as pure functions over `AgentState` slices.
- Integration-test control flow: safety block, clarification pause/resume, review gate enforcement
  (`tests/integration/test_crispr_gate.py`), partial-results degradation.

## Don't

- Don't hide control flow inside a node (no node that secretly loops the whole plan).
- Don't put model weights/inference in the graph — models are tools behind services
  (`tool_use_policy.md`).
- Don't let a node write the whole state back; return minimal deltas.
