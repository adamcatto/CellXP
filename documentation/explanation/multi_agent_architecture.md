# Multi-Agent Architecture

> Status: Draft v0.1. Explains the **multi-agent** design of CellXP: who the agents are,
> how they're layered, how they communicate, and when work is delegated to isolated sub-agents.
> Structural contract: `specs/agent/skill_plugin_contract.md`; harness decision: ADR-0008.
> `specs/agent/graph_spec.md` documents the compatibility workflow during migration.

## 1. It's a hierarchy, not a swarm

CellXP is a **hierarchical, harness-led multi-agent system** (ADR-0008), not a free-for-all of peer
agents negotiating. One mature harness adapter owns a turn; specialized skills and sub-agents do
bounded work through the policy kernel and return structured results into canonical run state. This
keeps the system auditable (one trace, one policy boundary) while preserving specialization and
context isolation.

Three layers:

| Layer | Agent(s) | Role | Implemented as |
|---|---|---|---|
| **L1 Harness** | planner/orchestrator | understand → plan → select skills → integrate → report | `HarnessAdapter` (Qwen Code first) |
| **L2 Skills/workflows** | `variant_effect`, `gwas`, `crispr`, `annotation`, `binding`, `structure`, `origami`, `rag`, `visualization` | execute one typed domain capability end-to-end | `SkillPlugin` over services; graph wrappers are temporary |
| **L3 Isolated sub-agents** | research, coding, optimization, design-search workers | deep, token-heavy subtasks that would pollute parent context | harness-native sandboxed sub-agents |

The harness can use distinct **reasoning roles** (risk, entity resolution, planning, critique,
reporting), but each deterministic or policy-sensitive operation is a typed skill/hook rather than
an invisible prompt convention.

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

- **Canonical results are the bus.** Agents do not message each other with raw transcripts; skills
  publish Steps, evidence, artifacts, statuses, and handles to the run store. The harness receives
  only bounded projections and decides the next move.
- **Subtask DAG is the contract.** The planner expresses cooperation as a `Subtask` DAG with
  `depends_on`; `task_selector` dispatches ready subtasks and loops until done
  (`graph_spec.md` §3, `nodes/task_selector.md`).
- **Isolated sub-agents return summaries, not transcripts.** An L3 sub-agent gets a scoped brief +
  sandboxed scratchpad, does its work, and writes back a compact result
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

- The **reasoning** layers (L1 harness roles, L3 sub-agents) run on the agent's reasoning LLM. The
  capable-GPU quality target is Qwen3.8-27B through a local OpenAI-compatible endpoint; modest
  hardware retains a smaller explicit profile (`specs/services/llm_service.md`).
- The **capability** agents (L2) are mostly **orchestrators of domain foundation models**
  (AlphaGenome, Evo 2, ESMFold, Boltz-2, …; `external_models_and_services.md`) — those models are
  tools, not agents. A capability agent's "intelligence" is mostly its pipeline + the reasoning LLM
  for glue/interpretation.

## 6. Relationship to mature harnesses

Qwen Code is the first adapter target because it already supplies planning, code/file tools, skills,
sub-agents, memory/compaction, hooks, MCP, sessions, and local OpenAI-compatible providers. Those
features remain behind `HarnessAdapter`; CellXP's external policy kernel controls biological tool
execution and actionable release. Deepagents, Prime Agent, Hermes, and other harnesses remain useful
comparison implementations, not dependencies of domain capabilities.

## 7. Open questions

- Qwen Code SDK vs headless stream protocol vs daemon transport for the production adapter.
- Which skill kinds may spawn sub-agents, and under which nested budgets?
- Cross-session "manager" agent for long-running projects (see `specs/agent/session_types.md`).

## 8. Related

`specs/agent/skill_plugin_contract.md` · `specs/agent/graph_spec.md` ·
`harness_and_context_engineering.md` ·
`specs/agent/session_types.md` · `specs/agent/control-flow/*` ·
ADR-0008 ·
`documentation/reference/external_models_and_services.md`.
