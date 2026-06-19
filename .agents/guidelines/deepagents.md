# deepagents Implementation Guidelines

`deepagents` is an opinionated agent harness on top of LangChain/LangGraph (planning + virtual
filesystem + sub-agents + context compaction + skills). We use it for **L3 isolated sub-agents** and
**filesystem-heavy work**, not to replace the hand-built L1 supervisor. Specs:
`documentation/explanation/multi_agent_architecture.md`, `harness_and_context_engineering.md`.

> Install: `pip install deepagents`. It runs on the LangGraph runtime, so checkpointing, streaming,
> and human-in-the-loop interoperate with our graph.

## When to use it

- **Sub-agents with isolated context** — literature sweeps, inverse-design/optimization loops, long
  multi-file assembly: run them in a `task` sub-agent so the supervisor's window stays clean
  (`multi_agent_architecture.md` §4).
- **Filesystem operations** — when a run must read/write/search many intermediate files (scratchpads,
  candidate sets, fetched documents), use the built-in filesystem tools instead of stuffing the
  prompt.
- **Context compaction** — long threads: rely on its summarize-and-offload-to-disk behavior.

Do **not** use it for a single deterministic model call (that's a capability **step**) or for the
safety-critical top-level ordering (that stays explicit LangGraph).

## Creating an agent / sub-agent

```python
from deepagents import create_deep_agent, SubAgent
from services.llm.factory import build_chat_model   # local Gemma via Ollama by default

researcher = SubAgent(
    name="literature-researcher",
    description="Searches and synthesizes primary literature with citations.",
    system_prompt=load_prompt("rag_subagent.md"),
    tools=[pubmed_search, fetch_record],            # + MCP tools where relevant
)

agent = create_deep_agent(
    model=build_chat_model(role="planner"),         # pass our LangChain model object
    tools=[...],
    system_prompt=load_prompt("supervisor_subagent.md"),
    subagents=[researcher],
    backend=...,                                      # see filesystem section
)
```

- **Pass our model object** (`build_chat_model(...)`) so sub-agents use the same local-first LLM and
  per-role overrides as the rest of the system (`langchain.md`). Don't hard-code a provider string.
- A default general-purpose sub-agent (with filesystem tools) always exists; add specialized
  `SubAgent`s for recurring jobs (researcher, optimizer, design-reviewer).
- Built-in tools you get for free: planning (`write_todos`) and filesystem
  (`ls`, `read_file`, `write_file`, `edit_file`, `glob`, `grep`).

## Filesystem backends (choose deliberately)

| Backend | Behavior | Use for |
|---|---|---|
| `StateBackend()` (default) | files live in LangGraph **state** (`files`), shared between supervisor & sub-agents, persisted in the checkpoint | run-scoped scratchpads, candidate sets, offloaded tool outputs |
| `FilesystemBackend(root_dir=...)` | real local disk | artifacts/files a user keeps; larger data |
| `StoreBackend()` | LangGraph **store** (durable, cross-thread) | **session/workspace memory** (`session_types.md`) |
| `CompositeBackend` | route paths to different backends | mix scratch (state) + durable (store) + disk |
| custom (`BackendProtocol`) | your rules | sandbox/object-store integration |

- Map our concepts: **run scratchpad → `StateBackend`**; **session memory → `StoreBackend`**;
  **persisted artifacts → `FilesystemBackend`/object store** (`specs/data/*`).
- Files a sub-agent writes to `StateBackend` remain available to the supervisor after the sub-agent
  finishes — use this to **return large results by reference** instead of inlining them.

## Filesystem permissions

- Declare read/write permission rules; give sub-agents the **narrowest** access they need. A
  literature sub-agent typically needs read on its inputs and write only to its result path.
- Never give a sub-agent write access to actionable outputs that bypass the review gate
  (`human_review_policy.md`).

## Context engineering with the filesystem

- **Offload, don't inline:** write big tool outputs to a file and pass the path; the model reads it
  on demand (`harness_and_context_engineering.md` §B2).
- Keep a per-run `plan.md`/`notes.md` scratchpad for multi-step work; let `write_todos` track progress
  (this complements our `Plan`/`Subtask`, it doesn't replace the audited plan in state).

## Streaming sub-agents

- Use `stream.subagents` so each delegated task has its own message/tool-call stream; map these into
  our activity surface (`streaming_protocol.md` §5) so the user sees "researching… (sub-agent)".

## Provenance & safety

- Sub-agent results still flow into our `evidence`/`artifacts` with full provenance
  (`state_schema.md` §8/§9) — a sub-agent doesn't get to skip citation/version recording.
- Sub-agents inherit the safety model; actionable output produced inside a sub-agent must still hit
  the human-review gate before it's recommended (`safety_model.md`, `human_review_policy.md`).

## Don't

- Don't run the top-level safety-first graph as a deep agent (keep L1 explicit).
- Don't default to `FilesystemBackend` on shared infra without permissions — prefer `StateBackend`
  for run scratch.
- Don't let sub-agents return raw transcripts; return distilled, cited results.
