# Harness Engineering & Context Engineering

> Status: Draft v0.1. Two disciplines that make the agent reliable: the **harness** (the scaffolding
> around the LLM) and **context engineering** (what we put in the LLM's window, and what we keep out).
> This is the **rationale**; the normative, testable requirements are in
> `specs/agent/harness_and_context_engineering.md`. Companion to `multi_agent_architecture.md`;
> implementation patterns in `.agents/guidelines/{langgraph,langchain,deepagents}.md`.

---

# Part A — Harness engineering

The **harness** is everything around the model that turns a stochastic next-token predictor into a
dependable system: the graph, the tools, structured I/O, validation, retries, budgets, and guardrails.
The model proposes; the harness disposes.

## A1. Principles

- **The graph is the harness.** Control flow lives in LangGraph (`graph_spec.md`), not in model free
  will. The model chooses *within* nodes; the harness decides *which* node runs, in what order, and
  what is allowed (safety-first ordering, the review gate).
- **Deterministic where possible, LLM where necessary.** Parsing, coordinate math, model dispatch,
  and scoring are deterministic code (`steps`); the LLM is used for classification, planning,
  interpretation, and writing. Don't ask the LLM to do arithmetic the harness can do exactly.
- **Structured I/O over free text.** LLM nodes return schema-validated JSON (Pydantic v2) — intents,
  plans, clarifications — so downstream code is robust (`.agents/guidelines/langchain.md`).
- **Every tool call is recorded.** Each model/tool/data call is a `Step` with tool+version+params+IO
  refs (`state_schema.md` §8) — the harness is also the provenance recorder (`FR-24`).

## A2. The tool layer

- Domain capabilities are tools behind the **service registry** (`tool_use_policy.md`); the agent
  selects among them by task/input/organism.
- Tool calls are **validated, retried, and bounded**: input adaptation per model, timeouts + backoff,
  fallbacks to alternates, and caching of pure calls (`tool_use_policy.md` §6/§7).
- **Heavy tools are async jobs** (Redis queue + GPU workers); the harness dispatches and integrates
  results without blocking the loop (`architecture_overview.md` §7, `control-flow/concurrency.md`).

## A3. Guardrails

- **Safety gate first** (`risk_classifier` before any capability) and **human-review gate** for
  actionable output — both are harness-enforced, not prompt-suggested (`safety_model.md`,
  `human_review_policy.md`).
- **Budgets** (`Budget`: tokens/wallclock/cost) bound loops and replanning; ceilings stop runaway
  inverse-design loops (`control-flow/replanning_and_budget.md`).
- **Graceful degradation**: recoverable errors append and the run continues with partial results
  (`NFR-6`).

## A4. Harness layers we build on

| Layer | What it gives us | We use it for |
|---|---|---|
| **LangGraph** | explicit graph runtime, state, checkpointing, interrupts, streaming | the L1 supervisor + capability subgraphs |
| **LangChain `create_agent`** | minimal tool-calling agent loop | simple single-capability agents where a full graph is overkill |
| **deepagents** | opinionated harness: planning, virtual filesystem, sub-agents, context compaction, skills | L3 isolated sub-agents + filesystem-heavy work |
| **LangSmith** | tracing, evals, datasets | observability + the post-training flywheel (`post_training.md`) |

---

# Part B — Context engineering

Context engineering is the practice of getting the **right tokens** into each model call — enough to
be correct, little enough to be cheap, focused enough to avoid distraction. The agent's quality is
bounded by what each node sees.

## B1. Principles

- **Minimal sufficient context per node.** Each LLM node receives a **slice** of `AgentState`, not
  the whole thing: `intent_classifier` gets the query + input summary; `planner` gets intent + risk +
  resolved entities + macro registry; `report_generator` gets reconciled evidence + citation map. We
  never dump the full transcript + all evidence into every call.
- **Organism + assembly + coordinates are always in context** for any positioned reasoning — these
  are never left implicit (`coordinate_systems.md`).
- **Evidence is packed, not pasted.** The report context contains compact evidence records
  (claim + value + confidence + citation id), not raw tool dumps.

## B2. Offloading & references (the filesystem trick)

Large or numerous tool outputs (genome-wide scans, multi-sequence sets, long papers, intermediate
design candidates) are **written to the virtual filesystem** (deepagents backend) and passed by
**reference**, not inlined into the prompt. The model reads a file only when it needs it (`read_file`/
`grep`/`glob`). This is how we keep long, multi-step runs within budget — see
`.agents/guidelines/deepagents.md`. In `AgentState`, heavy payloads already live behind
`storage_ref`/`output_ref` (`state_schema.md` §8/§10) — same idea.

## B3. Compaction & memory

- **Thread summarization.** Long conversations/runs are periodically summarized so the working context
  stays bounded; the full transcript remains in durable state for audit
  (deepagents context management; `state_schema.md` §18).
- **Scoped memory.** Within a run, the cursor + plan summarize "where we are". Across runs, a
  **session/workspace** carries durable memory (resolved entities, prior artifacts, defaults) via a
  persistent store backend (`specs/agent/session_types.md`).
- **Retrieval as context.** RAG injects only the top-ranked, claim-relevant passages (`rag`
  capability), with citations — retrieval is a context-engineering tool, not a dump.

## B4. Sub-agent context isolation

Spawning an L3 sub-agent gives a noisy subtask its **own** window; only its distilled result returns
to the supervisor (`multi_agent_architecture.md` §4). This is the strongest context-control lever we
have: the supervisor's context never sees the 40-paper sweep, just the synthesis.

## B5. Prompt assets

System/role prompts are versioned files in `agent/prompts/*` (not inline strings), so context is
reviewable and diffable, and so the post-training loop can correlate prompt versions with outcomes
(`post_training.md`).

## B6. Context budget checklist (per LLM call)

1. Which state slice does this node actually need?
2. Can any large input be referenced instead of inlined?
3. Is organism/assembly present if positions are involved?
4. Are evidence items packed (claim+confidence+citation) rather than raw?
5. Should this run as an isolated sub-agent to protect the main window?

## B7. Related

`multi_agent_architecture.md` · `post_training.md` · `specs/agent/state_schema.md` ·
`specs/agent/tool_use_policy.md` · `specs/agent/evidence_integration.md` ·
`specs/agent/session_types.md` · `coordinate_systems.md` ·
`.agents/guidelines/{langgraph,langchain,deepagents,langsmith}.md`.
