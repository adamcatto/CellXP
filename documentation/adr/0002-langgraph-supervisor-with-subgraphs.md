# ADR-0002 — LangGraph supervisor with capability subgraphs

- **Status:** Superseded for top-level orchestration by ADR-0008; retained as a compatibility
  workflow design during migration
- **Date:** initial agent design
- **Related:** `documentation/explanation/why_langgraph.md` (long-form companion),
  `documentation/explanation/architecture_overview.md` §5,
  `documentation/explanation/multi_agent_architecture.md`,
  `specs/agent/graph_spec.md`, `specs/agent/state_schema.md`,
  `specs/agent/capability-subgraphs/README.md`

## Context

CellXP is a multi-turn, multi-step copilot that has to: classify the user's intent and risk,
resolve biological entities, plan a chain of capabilities, dispatch heavy GPU jobs, integrate
typed evidence, run a critic, and gate actionable outputs behind human review — while
streaming progress to the user and surviving reconnects, pauses, and replanning. The system is
intrinsically **stateful, branching, interruptible, and observable**.

Several orchestration shapes were on the table:

1. **Hand-rolled state machine.** Maximum control; we own state, checkpointing, interrupts,
   replay. Maximum implementation cost; very easy to get checkpointing wrong.
2. **LangChain agent (`AgentExecutor` style).** Tool-calling loop with a single agent. Cheap
   to start, but the control flow is opaque, replanning is awkward, and pause/resume across
   user clarifications is not a first-class primitive.
3. **AutoGen / CrewAI.** Multi-agent frameworks. AutoGen is conversational-multi-agent first;
   CrewAI is role-based. Both make it harder to express "the supervisor decides what runs
   next" as a typed graph and harder to integrate the human-review gate as a structural pause.
4. **DSPy.** A compilation/optimization framework, not an orchestration runtime; complementary,
   not a replacement.
5. **LangGraph supervisor with subgraphs.** A typed graph with built-in checkpointing,
   interrupts, and subgraph composition. Subgraphs become natural "capability agents" the
   supervisor dispatches.

Selection criteria, in priority order: (a) first-class pause/resume + checkpointing for
human-in-the-loop runs, (b) typed shared state for provenance and the harness, (c) a clean
way to compose the L1/L2/L3 agent hierarchy (`multi_agent_architecture.md`), (d) the ability
to inspect and stream every node, and (e) ergonomic Python with the standard LLM ecosystem.

## Decision

Use **LangGraph** as the orchestration runtime, with a **top-level supervisor graph** that
delegates to **capability subgraphs**. Concretely:

- The L1 **supervisor graph** (`src/backend/cellxp/agent/graph.py`) handles input
  normalization, intent and risk classification, entity resolution, planning, task selection,
  evidence integration, critique, human-review gating, and report generation — each as a
  typed node (`specs/agent/nodes/*`).
- Each L2 **capability** (variant_effect, gwas, crispr, structure, binding, annotation, rag,
  visualization, origami) is a subgraph (`src/backend/cellxp/agent/subgraphs/*`) the
  supervisor dispatches via the planner/task-selector. Subgraphs are typed at their boundary
  (`specs/agent/capability-subgraphs/*.md`) and own their internal control flow.
- L3 **isolated sub-agents** (deepagents-style spawn) are an in-subgraph affordance for
  bounded exploration; they share the same `AgentState` schema but operate on a scoped slice.
- **Shared state** is a single Pydantic-typed `AgentState` (`specs/agent/state_schema.md`),
  not free-form dicts; nodes receive typed inputs and return typed updates.
- **Checkpoints** persist to Postgres for durable state and Redis for ephemeral state
  (`specs/serving/agent_runtime_serving.md` §5), so any replica can resume an awaiting-input
  or awaiting-review run from durable state.
- **Interrupts** are how the agent pauses for clarifications and review gates
  (`specs/agent/control-flow/pause_and_resume.md`, `specs/agent/human_review_policy.md`).

## Consequences

**Positive**

- Pause/resume across user clarifications and review gates is structural, not bolted on. A
  run can sit awaiting input for hours and resume cleanly from a different replica.
- Replanning, partial-success recovery, and budget-aware re-routing have a natural home
  (`specs/agent/control-flow/replanning_and_budget.md`).
- Every node execution is a `Step` with provenance (`specs/data/provenance_model.md` §4);
  streaming, audit, and reproduction are uniform across the graph.
- Subgraphs encapsulate capability-specific logic without exploding the supervisor; adding a
  capability is one subgraph plus a routing-policy update, not a graph rewrite.
- The hierarchical L1/L2/L3 model in `multi_agent_architecture.md` maps cleanly: supervisor =
  L1, subgraph = L2, spawned sub-agent = L3.

**Negative / accepted trade-offs**

- LangGraph is a young dependency; API churn is a real risk. Mitigated by isolating
  LangGraph-specific code in the agent layer and keeping the rest of the system behind the
  service interfaces (`specs/agent/state_schema.md`-typed I/O; services don't import
  LangGraph).
- The framework requires discipline around state shape: ad-hoc state mutations bypass typed
  reducers and break replay. The `state_schema.md` spec and code-review enforce typed updates.
- Some LangGraph patterns (sticky session, distributed checkpointer) require deliberate
  configuration; the `agent_runtime_serving.md` spec pins these down.

**Out of scope (deliberately not adopted)**

- A second orchestration framework alongside LangGraph for any production code path. If
  LangGraph becomes a blocker, we replace it; we do not run two orchestrators in parallel.
- Coupling business logic to LangGraph internals. Nodes are thin glue around typed services;
  porting the graph to a different runtime would be expensive but not architecturally
  impossible.

## Status notes

ADR-0008 records that revisit. The graph remains an executable compatibility workflow until the
skill kernel and mature harness adapter reach pause/resume, review, provenance, and replay parity.
New capabilities target typed skills first; they do not expand this graph into the product's general
coding/research harness.
