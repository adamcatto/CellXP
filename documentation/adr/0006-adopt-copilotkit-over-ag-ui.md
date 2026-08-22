# ADR-0006 — Adopt CopilotKit over a CellXP-owned AG-UI adapter

- **Status:** Accepted
- **Date:** 2026-08-22
- **Related:** `specs/planning/copilotkit_integration.md`, ADR-0008,
  `specs/interface/{api_contracts,streaming_protocol,artifact_model,interactive_panes}.md`,
  `documentation/adr/0002-langgraph-supervisor-with-subgraphs.md`

## Context

CellXP already owns the difficult backend contracts: typed scientific artifacts, ordered run
events, durable checkpoints, provenance, and kernel-enforced clarification/review pauses.
Its handwritten React chat implements those contracts but duplicates commodity chat behavior and
does not provide CopilotKit's polished chat shell, frontend-tool rendering, generative UI, or shared
agent-state hooks.

CopilotKit's open-source React/runtime packages communicate with agents through AG-UI. The stock
LangGraph/FastAPI adapter is not a safe drop-in for CellXP:

- CellXP's `AgentState` is richer than a messages-only agent state.
- CellXP's REST/SSE contract is already the portability boundary for non-React clients.
- As of this decision, CopilotKit documents graph interrupt rendering as unsupported by its
  LangGraph/FastAPI integration. Replacing CellXP's pause/resume path would weaken a non-bypassable
  safety invariant (`HARN-6`, ADR-0005).
- CellXP already persists sessions, runs, messages, checkpoints, artifacts, and audit events.
  Making a second thread store authoritative would create conflicting identities and retention
  policies.

## Decision

Use **CopilotKit v2** for the React chat/runtime layer and **AG-UI** as an additive protocol adapter.
CellXP's run store and policy kernel remain authoritative for state, persistence, safety, and
scientific data; the selected mature harness is replaceable.

Concretely:

1. Add a FastAPI AG-UI endpoint that translates between `RunAgentInput` and the existing CellXP
   session/run API. It emits standard AG-UI lifecycle, message, tool-call, state, and interrupt
   events.
2. Keep `/api/v1/sessions`, `/runs`, `/events`, `/artifacts`, clarification, and review endpoints
   canonical. Native and automation clients continue to use them unchanged.
3. Use a Next.js CopilotKit runtime route as the browser-facing broker. It points at the FastAPI
   AG-UI endpoint; it does not execute biology or hold scientific state.
4. Represent backend `Step`s as AG-UI tool calls and artifact availability as a
   `render_cellxp_artifact` tool call. Named CopilotKit renderers reuse CellXP's typed scientific
   panes rather than asking the LLM to generate plotting code or arbitrary components.
5. Publish a bounded state projection (run status, plan, artifact references, evidence summaries,
   and selected workspace context). Large payloads remain behind artifact IDs/storage references.
6. Translate CellXP clarification and review pauses to the standard AG-UI interrupt lifecycle.
   Resume payloads are correlated back to the original CellXP run and pass through the existing
   canonical checkpoint and audit path. Frontend-only or harness-native approval tools MUST NOT
   replace the review gate.
7. Start with CopilotKit OSS. Evaluate Enterprise Intelligence later for cross-device realtime
   threads and hosted inspection only. If adopted, CellXP IDs and retention policy remain
   authoritative and private sequence/artifact payloads stay in CellXP storage.

## Consequences

**Positive**

- A polished chat surface and generative/tool UI arrive without replacing scientific renderers.
- AG-UI becomes a standards-based browser adapter while the existing API remains portable.
- Runtime interrupts, provenance, review decisions, and artifact schemas retain one source of truth.
- CopilotKit or the mature harness can be replaced without changing typed capability skills.

**Negative / accepted trade-offs**

- The adapter must translate and test two event vocabularies.
- The initial local runtime may produce events in a burst because parts of the current graph are
  synchronous. True token/tool progress requires producers to emit during execution.
- CopilotKit's thread UI is not authoritative without the optional Intelligence platform; CellXP
  continues to own its session sidebar and history hydration.

## Rejected alternatives

- **Replace the CellXP API with CopilotKit's LangGraph adapter.** This loses current interrupt,
  artifact, audit, and non-React client guarantees.
- **Use frontend `useHumanInTheLoop` or harness approval as the safety gate.** Either is bypassable;
  actionable biology must remain policy-kernel-enforced.
- **Adopt Copilot Intelligence as the initial persistence layer.** It duplicates already-built
  state and introduces licensing/data-governance work before it provides a unique v1 capability.
- **Let the model emit arbitrary UI code.** Scientific views use registered, schema-validated
  renderers with accessible fallbacks; bounded A2UI may be evaluated only for layout composition.
