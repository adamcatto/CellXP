# Multi-Agent Architecture

> Status: Draft v0.1. Explains the **multi-agent** design of CellXP: who the agents are,
> how they're layered, how they communicate, and when work is delegated to isolated sub-agents.
> Structural contract: `specs/agent/graph_spec.md`; rationale for LangGraph: `why_langgraph.md`;
> implementation guidance: `.agents/guidelines/{langgraph,deepagents}.md`.

## 1. It's a hierarchy, not a swarm

CellXP is a **hierarchical, supervisor-led multi-agent system** (ADR-0002), not a free-for-
all of peer agents negotiating. One **supervisor** owns the run; specialized agents do bounded work
and return structured results into shared state. This keeps the system auditable (one trace, one
state) while still getting the benefits of specialization and context isolation.

Three layers:

| Layer | Agent(s) | Role | Implemented as |
|---|---|---|---|
| **L1 Supervisor** | the orchestrator | understand → plan → route → integrate → review → report | top-level LangGraph (`agent/graph.py`) |
| **L2 Capability agents** | `variant_effect`, `gwas`, `crispr`, `annotation`, `binding`, `structure`, `origami`, `rag`, `visualization` | execute one domain capability end-to-end | LangGraph **subgraphs** (`agent/subgraphs/*`, `capability-subgraphs/*`) |
| **L3 Isolated sub-agents** | research, optimization, design-search workers | deep, token-heavy subtasks that would pollute the main context | **deepagents `task` sub-agents** (spawned on demand) |

The supervisor itself is composed of **reasoning roles** that are effectively cooperating agents
sharing one state: `intent_classifier`, `risk_classifier`, `entity_resolver`, `planner`, `critic`,
`report_generator` (`specs/agent/nodes/*`). They are distinct prompts/personas with distinct jobs,
which is why we treat the supervisor as a small society rather than a single monolithic prompt.

## 2. Why multi-agent (vs one big prompt)

- **Specialization.** A planner prompt, a CRISPR-design pipeline, and a literature researcher need
  different instructions, tools, and context. Splitting them keeps each prompt focused and testable.
- **Context isolation.** A genome-wide scan or a 40-paper literature sweep produces huge intermediate
  context. Running it in an **isolated sub-agent** (its own window) and returning only a distilled
  result keeps the supervisor's context clean and cheap (`harness_and_context_engineering.md` §4).
- **Parallelism.** Independent capability agents run concurrently (e.g. `variant_effect` + `gwas` for
  one locus) under append-only state reducers (`graph_spec.md` §9, `control-flow/concurrency.md`).
- **Safety & review boundaries.** Actionable capability agents (`crispr`, `origami`, design) are the
  natural choke points for the human-review gate; isolating them makes the gate enforceable
  (`human_review_policy.md`).

## 3. Communication & coordination

- **Shared state is the bus.** Agents do not message each other ad hoc; they read/write the single
  `AgentState` (`state_schema.md`). The supervisor coordinates by reading capability outputs
  (`evidence`, `artifacts`, `Subtask.status`) and deciding the next move.
- **Subtask DAG is the contract.** The planner expresses cooperation as a `Subtask` DAG with
  `depends_on`; `task_selector` dispatches ready subtasks and loops until done
  (`graph_spec.md` §3, `nodes/task_selector.md`).
- **Isolated sub-agents return summaries, not transcripts.** An L3 sub-agent gets a scoped brief +
  scratchpad (a deepagents virtual-filesystem path), does its work, and writes back a compact result
  (evidence items + an artifact/file reference). The supervisor never ingests the sub-agent's full
  intermediate reasoning — only its conclusions and provenance.

## 4. When to spawn an L3 sub-agent

Spawn an isolated sub-agent (deepagents `task` tool) when a subtask is **deep, noisy, or
context-hungry** and its internals don't need to live in the main thread:

- **Literature research** — read/skim many sources, return a cited synthesis (`rag` capability).
- **Inverse-design / optimization loops** — propose→score→select over many candidate edits; only the
  Pareto-best candidates + scores return (`FR-18c`, `task_patterns.md` §6).
- **Long multi-file artifact assembly** — e.g. building a strain-engineering plan across many
  intermediate files on the virtual filesystem.

Do **not** spawn a sub-agent for a single deterministic model call — that's a normal capability
**step** (`state_schema.md` §8). Sub-agents are for branching, exploratory, or high-volume work.

## 5. Models behind the agents

- The **reasoning** layers (L1 supervisor roles, L3 sub-agents) run on the agent's reasoning LLM
  (default Gemma 4 4B via Ollama; `specs/services/llm_service.md`), with optional per-role model
  overrides (a stronger model for `planner`, a cheaper one for `report_writer`).
- The **capability** agents (L2) are mostly **orchestrators of domain foundation models**
  (AlphaGenome, Evo 2, ESMFold, Boltz-2, …; `external_models_and_services.md`) — those models are
  tools, not agents. A capability agent's "intelligence" is mostly its pipeline + the reasoning LLM
  for glue/interpretation.

## 6. Relationship to deepagents

We use **LangGraph** for the explicit, audited top-level graph (we need precise control of the
safety-first ordering and the review gate). We use **deepagents** as the **harness for sub-agents**:
its built-in planning (`write_todos`), virtual **filesystem** (offload/scratchpad), **sub-agent
spawning** (`task`), and **context compaction** are exactly what L3 work needs, without us
reinventing them. The two compose cleanly — deepagents is itself built on LangGraph
(`.agents/guidelines/deepagents.md`).

## 7. Open questions

- How much of the L1 supervisor should migrate onto deepagents middleware vs stay hand-rolled
  LangGraph? (Current lean: keep L1 explicit, use deepagents for L2-heavy/L3.)
- Should capability agents be allowed to spawn their own sub-agents, or only the supervisor?
- Cross-session "manager" agent for long-running projects (see `specs/agent/session_types.md`).

## 8. Related

`specs/agent/graph_spec.md` · `why_langgraph.md` · `harness_and_context_engineering.md` ·
`specs/agent/session_types.md` · `specs/agent/control-flow/*` ·
`.agents/guidelines/{langgraph,deepagents,langchain,langsmith}.md` ·
`documentation/reference/external_models_and_services.md`.
