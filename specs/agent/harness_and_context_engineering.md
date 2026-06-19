# Harness & Context Engineering — Spec

> Status: Draft v0.1 — **normative contract**. Defines testable requirements for the agent **harness**
> (the scaffolding around the LLM) and **context engineering** (what enters/leaves each LLM call).
> The narrative rationale is `documentation/explanation/harness_and_context_engineering.md`; this
> document is the requirements it must satisfy. RFC-2119 keywords (MUST/SHOULD/MAY). IDs are stable:
> `HARN-*` (harness), `CTX-*` (context). Implementation: `agent/*`, `services/llm/*`.

## 1. Scope

In scope: control-flow scaffolding, tool invocation discipline, structured I/O, guardrails, budgets,
and the rules governing what context each LLM-backed node/sub-agent receives and emits. Out of scope:
node behavior (`graph_spec.md`, `nodes/*`), model selection (`tool_use_policy.md`), and model training
(`specs/training/post_training.md`).

## 2. Harness requirements (`HARN-*`)

### HARN-1 Control flow is explicit
The run's control flow MUST be determined by the graph (`graph_spec.md`), not by model free choice.
LLM nodes decide **within** a node; the harness decides which node runs and in what order. The
safety-first ordering (`risk_classifier` before any capability) and the review gate MUST be
harness-enforced, not prompt-suggested.

### HARN-2 Deterministic-vs-LLM separation
Parsing, coordinate math, model dispatch, and numeric scoring MUST be deterministic code; the LLM MUST
NOT be relied upon for computations the harness can perform exactly. Violations are correctness bugs.

### HARN-3 Structured I/O at LLM boundaries
Every LLM-backed node that feeds downstream logic (intent, risk, plan, clarification, tool args) MUST
return schema-validated output (Pydantic v2). A validation failure MUST be treated as a **recoverable**
error: retry at most once with a repair hint, then degrade (`NFR-6`). The structured-output retry rate
MUST be recorded (post-training signal, `specs/training/post_training.md`).

### HARN-4 Every external call is a recorded Step
Every model/tool/data/transform call MUST be recorded as a `Step` with `tool`, `tool_version`,
`params`, and input/output refs (`state_schema.md` §8). No "silent" tool calls (`FR-24`).

### HARN-5 Tool invocation discipline
Tool/model calls MUST: adapt inputs per the target's contract (`tool_use_policy.md`), enforce
timeouts + bounded retries with backoff, support declared fallbacks, and cache pure calls keyed by
inputs+version. Heavy (`weight="heavy"`) calls MUST dispatch as async jobs and MUST NOT block the
top-level loop (`control-flow/concurrency.md`).

### HARN-6 Guardrails are non-bypassable
The safety gate (`safety_model.md`) and the human-review gate (`human_review_policy.md`) MUST NOT be
disabled, reordered after capabilities, or bypassed by any node, sub-agent, session setting, or prompt.

### HARN-7 Budgets bound the run
Every run MUST carry a `Budget` (tokens/wallclock/cost; `state_schema.md` §15). The harness MUST check
budget before dispatch and before each loop iteration, and on exhaustion MUST stop dispatch and
proceed to integrate + report partial results (`control-flow/replanning_and_budget.md`).

### HARN-8 Graceful degradation
A recoverable error MUST append to `errors`, mark the subtask `failed`, and allow the run to continue
with partial results; only a fatal error sets `status=failed` (`NFR-6`).

### HARN-9 Harness layering
The harness MUST be built on the sanctioned stack: LangGraph for the L1 supervisor + capability
subgraphs; `langchain.create_agent` permitted for simple single-capability agents; `deepagents` for
L3 sub-agents and filesystem-heavy work (`multi_agent_architecture.md`,
`.agents/guidelines/{langgraph,langchain,deepagents}.md`). New harness layers MUST be added by ADR.

## 3. Context-engineering requirements (`CTX-*`)

### CTX-1 Minimal sufficient context
Each LLM call MUST receive only the `AgentState` **slice** it needs, not the whole state or full
transcript. Node-level context contracts (what each node reads) are defined in `nodes/*` and MUST be
honored.

### CTX-2 Coordinates/organism always present
Any LLM call performing positioned reasoning MUST include organism + assembly + coordinate convention
in context (`coordinate_systems.md`). Positioned reasoning without these is prohibited.

### CTX-3 Evidence is packed, not pasted
Report/critique context MUST contain compact evidence records (claim + value + confidence + citation
id), not raw tool dumps (`evidence_integration.md`).

### CTX-4 Offload large payloads by reference
Large or numerous tool outputs (genome-wide scans, multi-sequence sets, long documents, candidate
sets) MUST be persisted (virtual filesystem / object store) and passed by **reference**
(`storage_ref`/`output_ref` or a deepagents FS path), never inlined into the prompt
(`.agents/guidelines/deepagents.md`). Inlining multi-MB payloads into state/events is prohibited.

### CTX-5 Compaction with durable retention
Long threads/runs SHOULD be summarized to keep working context bounded, but the full transcript/trace
MUST remain in durable state for audit (`state_schema.md` §18). Compaction MUST NOT drop
provenance-relevant data.

### CTX-6 Scoped memory
Within-run "where we are" MUST be expressed via `plan`/`cursor`. Cross-run recall MUST be carried by
the session/workspace memory (`session_types.md`) via a durable store backend, with privacy governed
by `specs/data/*`.

### CTX-7 Retrieval is selective
RAG context MUST inject only top-ranked, claim-relevant passages **with citations**; bulk-dumping a
corpus into context is prohibited (`capability-subgraphs/rag.md`).

### CTX-8 Sub-agent context isolation
Token-heavy/noisy subtasks SHOULD run as isolated L3 sub-agents whose internal context does NOT enter
the supervisor; only distilled, cited results return (`multi_agent_architecture.md` §4).

### CTX-9 Prompts are versioned assets
System/role prompts MUST live as versioned files in `agent/prompts/*` (not inline literals) so context
is reviewable, diffable, and correlatable with outcomes for post-training.

## 4. Acceptance criteria

A change satisfies this spec when:
- LLM-boundary outputs are schema-validated with a measured retry rate (`HARN-3`).
- Tests confirm safety/review gates cannot be bypassed by a sub-agent or session setting (`HARN-6`).
- Budget exhaustion yields a partial report, not a crash (`HARN-7`, `HARN-8`).
- A context-budget review of each LLM node shows it receives only its declared slice, with
  organism/assembly present for positioned calls (`CTX-1`, `CTX-2`).
- Large outputs appear as references in state/events, not inlined blobs (`CTX-4`).
- Prompt assets are files under `agent/prompts/` (`CTX-9`).

## 5. Open questions

- How much of the L1 supervisor migrates onto deepagents middleware vs stays explicit LangGraph.
- Standard compaction trigger (token threshold) and summary schema.
- Per-node context-slice contracts: centralize in one table vs keep in each `nodes/*` file.

## 6. Related

`documentation/explanation/harness_and_context_engineering.md` (rationale) ·
`multi_agent_architecture.md` · `graph_spec.md` · `state_schema.md` · `tool_use_policy.md` ·
`control-flow/*` · `session_types.md` · `specs/training/post_training.md` ·
`.agents/guidelines/{langgraph,langchain,deepagents}.md`.
