# ADR-0008 — Adopt a harness-neutral skill kernel and Qwen Code as the first adapter

- **Status:** Accepted; kernel foundation implemented, harness adapter pending evaluation
- **Date:** 2026-08-22
- **Supersedes:** ADR-0002 for top-level orchestration; ADR-0007's LangGraph-first decision
- **Retains:** ADR-0005 review guarantees; ADR-0006 CopilotKit/AG-UI boundary; ADR-0007's
  Qwen3.8 quality-model decision
- **Related:** `specs/agent/harness_and_context_engineering.md`,
  `specs/agent/skill_plugin_contract.md`, `specs/planning/copilotkit_integration.md`

## Context

CellXP's current LangGraph supervisor made deterministic workflow, checkpoint, clarification, and
review behavior executable early. It is not, however, a complete coding/research harness. Building
Codex/Claude-Code-like planning, filesystem work, sub-agents, memory, compaction, and rich tool
approval directly into the graph would duplicate mature harness functionality and increasingly
couple biological capabilities to one control-flow framework.

The inverse extreme is also unsafe: exposing model workers and actionable biological tools directly
to a general agent loop would make safety ordering, coordinate validation, provenance, budgets, and
human review dependent on prompts or vendor hooks. Hooks run inside the selected harness and cannot
be the sole security boundary.

Qwen Code is the first adapter target because its current open-source runtime has:

- headless and SDK modes with line-delimited `stream-json` events;
- skills, sub-agents, lifecycle/tool hooks, MCP, sessions, and sandbox support;
- OpenAI-compatible model providers, including local vLLM/Ollama endpoints;
- a coding-oriented loop that can be rendered through CellXP's existing AG-UI boundary.

Its bidirectional stream protocol and long-running daemon path still require integration testing.
Headless approval prompts also fail closed, and unrestricted auto-approval does not imply sandboxing.
CellXP therefore must not run it with unrestricted `--yolo` host access or treat its approval mode
as biological authorization.

## Decision

1. The stable runtime boundary is a **harness-neutral skill kernel**, not a LangGraph graph. A
   `HarnessAdapter` consumes user turns and emits canonical CellXP events; typed `SkillPlugin`s are
   the only way a harness invokes biological capabilities.
2. Biological services, deterministic transforms, and reusable scientific workflows become
   versioned skills with bounded Pydantic inputs and typed, provenance-bearing results. Existing
   LangGraph capability nodes may run behind a compatibility adapter while logic is extracted; raw
   `AgentState` is never exposed as model tool input.
3. A CellXP-owned **policy kernel** wraps every skill invocation outside the harness. It enforces
   risk clearance, authorization, budgets, coordinate requirements, provenance, and withholding of
   actionable outputs pending review. Harness hooks duplicate these checks for fast feedback but
   cannot weaken or replace them.
4. **Qwen Code is the first mature harness adapter to implement and evaluate.** The adapter will use
   its SDK or headless `stream-json` protocol, connect to CellXP skills through an authenticated
   in-process/MCP bridge, and use the self-hosted Qwen3.8 OpenAI-compatible profile. The interface
   remains pluggable so another harness can replace it without changing skills, policy, artifacts,
   or AG-UI.
5. LangGraph remains temporarily as the **compatibility workflow adapter** for implemented
   supervisor and capability flows. It is no longer the target product harness or the architectural
   source of truth. Migration proceeds capability-by-capability, with parity tests before a graph
   path is retired.
6. CopilotKit and AG-UI remain the experience/event layer. Harness-native events are normalized to
   canonical run, step, evidence, artifact, clarification, and review events before reaching the UI.
7. Coding and shell tools run in a per-run sandbox with explicit filesystem/network scopes and
   budgets. Biological actions are not approved by generic file-edit or shell approval.

## Migration sequence

1. Land skill/plugin contracts, registry, policy hooks, and a bounded compatibility adapter.
2. Publish read-only and analytical capabilities as model-visible skills; expose large payloads by
   reference through audited readers.
3. Add the Qwen Code adapter and event translator behind a deployment flag; run it against recorded
   protocol fixtures and the current graph for parity.
4. Move planning, critique, context compaction, coding, and research loops to the mature harness.
5. Retain deterministic workflow plugins where an explicit state machine is useful; remove the
   top-level LangGraph supervisor only after pause/resume, cancellation, replay, and review parity.

## Evaluation gate

The Qwen Code adapter cannot become the default until tests show:

- 100% safety and actionable-review enforcement when the harness, prompt, or hook attempts bypass;
- valid skill arguments/results and complete Step/evidence/artifact provenance;
- durable resume, cancellation, replay, idempotency, and bounded context behavior;
- improved long-horizon biology and coding scores over the compatibility graph;
- acceptable time-to-first-event and end-to-end latency at the target concurrency;
- no unsandboxed file, shell, network, MCP, or generated-code execution.

## Consequences

**Positive**

- CellXP can adopt a mature agent experience without rewriting scientific capabilities per harness.
- Domain services, safety policy, artifacts, and provenance remain stable and independently testable.
- Deterministic workflows stay available as plugins instead of dictating every conversational turn.

**Negative / accepted trade-offs**

- The migration temporarily maintains a graph compatibility path and a new skill path.
- Qwen Code's event, permission, and session protocols add an adapter surface that must be pinned and
  contract-tested.
- Policy checks may be duplicated in harness hooks and the authoritative kernel; the kernel always
  wins.

## Rejected alternatives

- **Keep expanding LangGraph into a coding harness.** This duplicates mature sandbox, skill,
  sub-agent, memory, and coding-loop functionality and makes the UI/runtime harder to replace.
- **Let Qwen Code invoke workers directly.** Its hooks and approvals are not sufficient biological
  policy boundaries and may be disabled or configured incorrectly.
- **Replace everything in one cutover.** The current graph contains tested pause/review behavior;
  removing it before parity would regress safety and durable run semantics.

## References

- Qwen Code headless/streaming: `https://qwenlm.github.io/qwen-code-docs/en/users/features/headless/`
- Qwen Code hooks: `https://qwenlm.github.io/qwen-code-docs/en/users/features/hooks/`
- Qwen Code MCP: `https://qwenlm.github.io/qwen-code-docs/en/users/features/mcp/`
- Local OpenAI-compatible providers:
  `https://qwenlm.github.io/qwen-code-docs/en/users/configuration/model-providers/`
