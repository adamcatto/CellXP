# Why LangGraph

> Long-form companion to **ADR-0002**. The ADR is the decision and the trade-offs; this
> document is the why-it-fits in narrative form, written for a contributor who is new to the
> codebase and asking the very reasonable question "why this framework, in this place, at
> this stage?" Structural contract: `specs/agent/graph_spec.md`. Practical implementation
> patterns: `.agents/guidelines/langgraph.md`.

## 1. The shape of the problem

CellXP is not a one-shot LLM call wrapped in a chat UI. A typical user turn involves: parsing
a query, classifying intent and risk, resolving biological entities against a reference
service, planning a chain of capability invocations, running multiple GPU jobs in parallel,
fusing typed evidence from them, deciding whether to clarify with the user, deciding whether
to gate the output for human review, writing a report with live citations, and streaming all
of it back over SSE. Then the user clicks "approve" on a candidate, and the run resumes from
exactly where it paused — possibly hours later, possibly on a different replica.

That problem has four properties:

1. **Stateful** — the system has to remember a structured `AgentState` across many steps and
   across pauses.
2. **Branching** — the graph of "what runs next" depends on intent, risk, available
   capabilities, partial results, and budgets.
3. **Interruptible** — the system has to pause for clarifications and review gates as a
   first-class behavior, not a hack on top of a tool-calling loop.
4. **Observable** — every step has to be inspectable, streamable, and reproducible.

LangGraph happens to be designed around exactly those four properties.

## 2. What LangGraph actually gives us

A short, honest list — what we use, in roughly the order it matters:

- **Typed state with reducers.** `AgentState` is one Pydantic object; nodes return updates
  that are merged via explicit reducers (append-only lists for evidence/steps/artifacts,
  overwrite for status/plan). This makes parallel-subgraph results compose without us hand-
  rolling a CRDT (`specs/agent/state_schema.md`, `graph_spec.md` §9).
- **Subgraphs.** Each L2 capability is a self-contained subgraph the supervisor invokes by
  name; the subgraph has its own internal graph but presents a single boundary to the
  supervisor (`specs/agent/capability-subgraphs/README.md`). We get isolation without
  multiplying frameworks.
- **Checkpointers.** Persistence of run state to Postgres (durable) and Redis (ephemeral) is
  a configuration concern, not a thing we wrote. A run that pauses for human review still
  exists, on disk, in a typed shape another replica can resume from
  (`specs/serving/agent_runtime_serving.md` §5).
- **Interrupts.** A node can yield `interrupt(...)` and the run cleanly enters
  `awaiting_input` or `awaiting_review`; an external POST resumes execution at the same node
  with the answer (`specs/agent/control-flow/pause_and_resume.md`). This is the single most
  load-bearing primitive for the human-review gate (`ADR-0005`).
- **Streaming.** `stream_events` produces the typed events we surface as SSE
  (`specs/interface/streaming_protocol.md`). We didn't invent the framing; we mapped it.
- **Conditional edges.** "Did the critic pass? if not, replan" is one edge with a predicate,
  not a hand-rolled state machine. It also makes the graph drawable, which makes review
  conversations sane.

## 3. What we deliberately don't use from LangGraph or its neighbors

- **No `AgentExecutor`-style hidden tool loop.** Every tool call is an explicit step in the
  graph with a typed input/output and a `Provenance` record. We chose the more explicit path
  because the agent's tool calls are the things that *cost money and matter biologically* —
  hiding them in a loop would defeat the audit trail.
- **No reliance on prompt-only safety.** Safety lives in the graph: `risk_classifier` early,
  `human_review_gate` at the actionable boundary (`ADR-0005`,
  `specs/agent/human_review_policy.md`). LangGraph gives us the structural pause point;
  prompt-level guardrails are defense-in-depth, not the gate.
- **No "free-for-all" multi-agent negotiation.** We pick the hierarchical supervisor pattern
  (`documentation/explanation/multi_agent_architecture.md` §1), where the L1 supervisor owns
  the run and L2/L3 agents do bounded work. Other LangGraph patterns (peer-to-peer agent
  graphs, dynamic spawning of arbitrary agents) are deliberately not the default — they cost
  observability we are unwilling to spend.
- **Heavy weights inside graph nodes.** Domain-model inference (Boltz, ESMFold, AlphaGenome)
  runs in **workers** dispatched via Redis (`specs/serving/domain_model_serving.md`), not in
  LangGraph nodes themselves. Nodes orchestrate; workers compute.

## 4. The alternatives, and why we passed

- **Hand-rolled state machine.** Maximum control, maximum cost. We'd be writing
  checkpointers, replay logic, interrupt semantics, and a typed-update merge story from
  scratch. The framework is doing the boring-and-easy-to-get-wrong parts for us.
- **LangChain `AgentExecutor`-style tool loop.** Cheap to spin up; opaque to debug; replanning
  is awkward; pause/resume across user clarifications is not a first-class primitive. We
  outgrow it on the first capability that needs multiple parallel sub-steps with shared state.
- **AutoGen.** Conversational multi-agent first. CellXP isn't agents-chatting-with-agents;
  it's a supervisor running a planned execution against typed services. AutoGen's defaults
  point at a different shape.
- **CrewAI.** Role-based abstractions ("researcher", "writer", "critic") on top of LangChain.
  Pleasant for prototyping; awkward when the agent hierarchy is hierarchical (supervisor +
  capability + isolated sub-agent) and not just "a crew."
- **DSPy.** A compilation/optimization framework for prompts and chains, not an orchestration
  runtime. It is complementary — we may use DSPy-style compiled prompts inside LangGraph
  nodes — but it doesn't replace LangGraph.
- **Custom orchestration on top of a queue.** Tempting, but most of what we'd build is what
  LangGraph already gives us: typed state, interrupts, subgraphs, checkpointers.

## 5. How the LangGraph choice shows up in code (and in the specs)

The framework choice is visible in a few specific places. None of them are accidents:

- **`src/backend/cellxp/agent/graph.py`** — the supervisor graph, compiled at import time. Its
  shape mirrors `specs/agent/graph_spec.md`; nodes are imported from `agent/nodes/`.
- **`src/backend/cellxp/agent/subgraphs/<capability>/`** — one directory per L2 capability;
  each defines its subgraph and registers it with the supervisor.
- **`src/backend/cellxp/agent/state.py`** — the Pydantic `AgentState`. Reducers are the
  contract for how parallel subgraph updates compose (`graph_spec.md` §9).
- **`agent/checkpoint.py`** — the Postgres + Redis checkpointer wiring. Not a node; a
  configuration of LangGraph's persistence layer
  (`specs/serving/agent_runtime_serving.md` §5).
- **`agent/streaming.py`** — adapts LangGraph's event stream to the typed SSE envelopes in
  `specs/interface/streaming_protocol.md`.

The rest of the codebase **does not know LangGraph exists**. Services depend on
`langchain-core` message primitives at most (for prompt construction); the FastAPI layer
treats the agent as `run(input) -> async stream of typed events`; the interface layer cares
only about the SSE wire. This is the deliberate firewall: LangGraph is the orchestration
runtime, not a pervasive dependency.

## 6. What we accept by choosing it

- **API churn.** LangGraph is young. We isolate it to the agent layer and we keep the
  abstractions thin enough to replace if we ever have to.
- **Discipline cost.** Typed-state + reducers means we can't sneak ad-hoc state mutations
  into nodes. The `AgentState` spec and code review enforce this; the payoff is replay and
  parallel composition that actually work.
- **Learning curve.** New contributors have one more framework to learn. The
  `.agents/guidelines/langgraph.md` doc + the per-node specs in `specs/agent/nodes/*` are
  the ramp.

## 7. Where to go from here

- **For the structural contract** (state, graph, nodes, control flow, capability subgraphs):
  `specs/agent/`.
- **For multi-agent layering** (L1/L2/L3, when to spawn an isolated sub-agent):
  `documentation/explanation/multi_agent_architecture.md`.
- **For harness / context engineering** (how the LLM-backed nodes manage context):
  `documentation/explanation/harness_and_context_engineering.md`.
- **For practical patterns** (how to add a node, how to compose subgraphs, what to avoid):
  `.agents/guidelines/langgraph.md`, `.agents/guidelines/deepagents.md`.
- **For the deployment shape** (replicas, checkpointers, sticky SSE):
  `specs/serving/agent_runtime_serving.md`.
- **For the decision and trade-offs in normative form:** `documentation/adr/0002-langgraph-supervisor-with-subgraphs.md`.
