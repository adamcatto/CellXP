# CopilotKit, AG-UI, and Reasoning-Harness Integration Plan

> Status: **Phase A foundation implemented; harness migration foundation in progress**. Accepted
> decisions: ADR-0006, ADR-0007 (model), and ADR-0008. This plan preserves CellXP's canonical
> REST/SSE, artifact, provenance, safety, and review contracts while replacing LangGraph-first
> orchestration with typed skills behind a mature harness adapter.

## 1. Outcome

CellXP should feel like a modern coding agent adapted to biology:

- CopilotKit's polished, streaming chat shell;
- visible plans and live tool activity with concise defaults and inspectable details;
- inline and docked AlphaGenome tracks, locus plots, contact maps, structures, guide tables, and
  evidence—not JSON dumps;
- a shared session workspace where selections/artifacts from the UI become bounded context for the
  next turn;
- kernel-enforced clarification and actionable-biology review cards;
- a capable, private reasoning model for planning, synthesis, and code work;
- long-running research/code tasks that can use files and sub-agents without contaminating the
  supervisor context or bypassing safety/provenance.

This is an interface and harness upgrade, not a license to move scientific transforms into React or
let an LLM replace deterministic coordinate/model code.

## 2. Target architecture

```text
CopilotChat + registered biology renderers + workspace dock
        │
        │ /api/copilotkit (same-origin)
        ▼
Next.js CopilotKit runtime (auth/context broker; no biology)
        │
        │ AG-UI
        ▼
FastAPI AG-UI adapter ───────────────────┐
        │                                │ canonical IDs/events
        ▼                                ▼
CellXP run runtime / policy kernel / artifact API
        │
        ▼
HarnessAdapter (Qwen Code first; compatibility graph during migration)
        │
        ├── typed SkillPlugins / deterministic workflow plugins
        │      └── biology services and GPU workers
        ├── provider-agnostic reasoning LLM
        │      └── Qwen3.8-27B quality profile (vLLM/SGLang)
        └── sandboxed code/files/sub-agents
```

There are two wire contracts by design:

1. CellXP REST/SSE remains canonical and portable to native/CLI clients.
2. AG-UI is the browser-agent interaction adapter consumed by CopilotKit.

The adapter maps, but does not redefine, run identity, scientific state, or review policy.

## 3. Event and rendering map

| CellXP source | AG-UI representation | CopilotKit / workspace rendering |
|---|---|---|
| run lifecycle | `RUN_STARTED`, `RUN_FINISHED`, `RUN_ERROR` | chat run state |
| report/message deltas | `TEXT_MESSAGE_*` | streamed markdown answer |
| `Step` start/result | `TOOL_CALL_*` + result | branded live tool card; details on demand |
| reasoning summary | `REASONING_*` where policy permits | collapsed reasoning summary |
| plan/status/evidence refs | bounded `STATE_SNAPSHOT` / deltas | plan, evidence, run inspector |
| artifact ref | `render_cellxp_artifact` tool call | inline preview + open/focus typed dock pane |
| clarification | interrupt, `reason=input_required` | option/free-text card |
| actionable review | interrupt, `reason=tool_call` or `confirmation` | candidate/risk/evidence approval card |
| selection/pinned context | UI-owned read-only context / bounded shared state | next-turn context by artifact/coordinate ref |

Scientific renderers bind only to registered artifact payload schemas. The model may choose which
registered view to show; it may not invent values or executable React code. A2UI is limited to
layout over an allowlisted catalog after the typed renderer path is stable.

## 4. Shared-state boundary

The AG-UI state projection is deliberately smaller than `AgentState`:

```json
{
  "cellxp": {
    "session_id": "…",
    "run_id": "…",
    "status": "running",
    "plan": {"revision": 2, "subtasks": []},
    "artifacts": [{"id": "…", "type": "structure_3d", "status": "ready"}],
    "evidence": [{"id": "…", "source": "alphagenome", "summary": "…"}],
    "pending_interaction": null,
    "model": {"provider": "openai_compatible", "name": "Qwen/Qwen3.8-27B"}
  },
  "workspace": {
    "selected_artifact_ids": [],
    "selection": null,
    "pinned_entity_ids": []
  }
}
```

- Backend-owned fields are read-only in the browser.
- UI selection/viewport state stays ephemeral (`PNS-9`) and enters a run only as explicit bounded
  context; it does not mutate a scientific artifact.
- Artifact payloads, raw sequences, coordinates arrays, structures, and tool dumps remain behind
  IDs/storage references (`CTX-4`, `ART-2`).
- Every context reference is authorized against the session before harness/skill execution.

## 5. Delivery phases

### Phase A — protocol and chat foundation (implemented)

- Add the Next.js CopilotKit v2 runtime and chat component.
- Add a custom FastAPI AG-UI endpoint over the CellXP runtime.
- Project lifecycle, answer, steps, artifacts, evidence, and run state into standard AG-UI events.
- Reuse the current artifact dock/renderers from named CopilotKit tool renderers.
- Preserve the current REST/SSE chat behind a development fallback until browser journeys pass.

**Exit:** a normal query can create a CellXP run from CopilotChat, show the answer and tool activity,
and open every emitted artifact in the typed dock. API and AG-UI contract tests pass without external
models.

### Phase B — shared state and kernel-enforced HITL

- Emit state snapshots before every pause.
- Translate clarification/review to AG-UI interrupt outcomes and correlate `resume[]` to the existing
  CellXP run/checkpoint.
- Render the current clarification and review cards through `useInterrupt`.
- Publish selections and pinned artifact/entity refs as bounded next-turn context.
- Hydrate chat history from CellXP sessions; do not depend on Copilot Intelligence.

**Exit:** clarification and review survive reconnect/restart; duplicate resumes are idempotent;
actionable artifacts cannot become recommendations or exports before audited approval.

### Phase C — true progressive execution

- Emit run events while harness steps/skills execute instead of reconstructing them from the
  terminal snapshot.
- Stream reasoning summaries and report tokens from provider callbacks.
- Emit artifact placeholders before jobs and revisions as payloads/exports become ready.
- Add cancellation propagation through AG-UI → runtime → harness/skill/job workers.
- Add backpressure, replay, and large-session virtualization.

**Exit:** p95 visible state change remains under 2 s during long jobs; reconnect replays durable
events in order; no multi-megabyte payload appears in AG-UI or agent state.

### Phase D — Qwen3.8 quality profile

- Implement the provider abstraction currently specified but not yet present under
  `services/llm/`.
- Add an OpenAI-compatible vLLM/SGLang profile for `Qwen/Qwen3.8-27B` with the official
  `qwen3` reasoning parser and `qwen3_coder` tool parser, pinned model revision, prefix caching,
  and bounded concurrency.
- Add per-role reasoning effort/token ceilings; start with one loaded model to avoid swaps.
- Make LLM-backed nodes consume schema-validated outputs with one repair retry.
- Compare against the current local baseline and at least one opt-in frontier provider on biology,
  coding, structured-tool, safety, latency, and long-context evals.

**Exit:** the quality profile clears ADR-0007's evaluation gate. The modest-hardware local profile
continues to work and remote fallback never occurs silently.

### Phase E — harness-neutral skills and Qwen Code adapter

- Land `SkillPlugin`, registry, policy-hook, and `HarnessAdapter` contracts; wrap implemented
  LangGraph capability nodes only through bounded compatibility inputs.
- Publish analytical capabilities through an authenticated in-process/MCP bridge. The policy
  kernel—not Qwen hooks—enforces risk, authorization, provenance, coordinates, budgets, and review.
- Add a pinned Qwen Code SDK/headless `stream-json` adapter with partial event translation, selective
  artifact readers, task budgets, compaction, and isolated sub-agents.
- Run code/shell/files in per-run sandboxes without unrestricted auto-approval or ambient network.
- Return typed claims, evidence IDs, produced file/artifact refs, limitations, and next actions; do
  not inject internal sub-agent transcripts into parent context.
- Feed generated analyses through the normal evidence/artifact pipeline so later turns reason from
  durable handles.

**Exit:** long-horizon biology+coding golden tasks improve without regressions in provenance,
coordinate correctness, resource ceilings, or safety.

### Phase F — optional Enterprise Intelligence decision

Run a time-boxed evaluation only when CellXP needs cross-device realtime threads, collaborative
rejoin, or the hosted inspector. Compare cloud-hosted and self-hosted data residency, license/ops
cost, identity mapping, deletion/retention, and duplicate persistence. OSS remains supported.

**Exit:** adopt through a separate ADR or explicitly reject/defer. No sequence or artifact data is
sent to a hosted platform without policy, consent, and audit coverage.

## 6. Model and harness policy

- **Production authority:** CellXP's run store and policy kernel around typed skills; no harness is
  allowed to bypass them.
- **Mature harness:** Qwen Code is the first adapter target; LangGraph is a temporary compatibility
  workflow during parity migration.
- **Quality model:** Qwen3.8-27B on an explicit capable-GPU profile, not an unconditional laptop
  default.
- **Fast path:** low reasoning effort and compact context for classification/routing; the harness
  may choose a deterministic workflow skill for trivial turns.
- **Deep path:** higher reasoning budget and isolated research/code sub-agents only when the plan
  needs them.
- **Prime/Hermes:** comparison/reference designs. Their useful patterns remain portable because
  CellXP capabilities live behind harness-neutral interfaces.
- **Context loop:** tools write canonical artifacts/evidence; context builders inject bounded
  summaries + handles; the model requests deeper slices through audited tools.

## 7. Verification

Required deterministic coverage:

- AG-UI request/event schema and ordering contract tests;
- session/run ID and resume correlation, replay, idempotency, and cancellation;
- artifact tool-call rendering for every registered type plus accessible fallback;
- shared-state size/redaction tests and authorization of referenced artifacts;
- browser journeys for text streaming, AlphaGenome track, structure pane, clarification, review,
  rejection/request changes, failure, reconnect, and reduced-motion/axe checks;
- safety tests proving frontend tools, A2UI, harness hooks, skills, sub-agents, and session state
  cannot bypass kernel gates;
- Qwen Code stream fixture tests for text/tool/progress events, cancellation, failure, and resume;
- model evals for structured output/tool validity, biology correctness, coding, long-horizon
  completion, latency, and token/cost budgets.

No live model, hosted CopilotKit, or GPU service is required for pull-request tests; recorded
protocol fixtures and fake providers cover the integration.

## 8. Main risks and controls

| Risk | Control |
|---|---|
| two event models drift | one typed translator + contract fixtures; CellXP remains canonical |
| polished UI hides provenance | default concise cards always deep-link to run/evidence/artifact |
| frontend or harness approval bypasses policy | only canonical kernel review decisions can release actionable biology |
| shared state leaks raw sequence/tool output | bounded projection, refs only, authorization/redaction tests |
| 27B model is slow or unavailable | explicit hardware profiles, reasoning budgets, measured fallback profile |
| model context becomes a raw artifact dump | selective context builder and audited lazy readers |
| harness hooks/config bypass budgets/safety | external policy kernel, typed return, sandbox, immutable policies |
| hosted thread platform duplicates state | OSS first; separate adoption ADR and data-governance review |

## 9. Source references

- CopilotKit architecture and OSS/Enterprise boundary:
  `https://docs.copilotkit.ai/langgraph-fastapi/concepts/architecture`,
  `https://docs.copilotkit.ai/langgraph-typescript/concepts/oss-vs-enterprise`
- CopilotKit generative UI, shared state, and HITL:
  `https://docs.copilotkit.ai/generative-ui/tool-rendering`,
  `https://docs.copilotkit.ai/langgraph-fastapi/shared-state`,
  `https://docs.copilotkit.ai/human-in-the-loop`
- AG-UI server and interrupt protocol:
  `https://docs.ag-ui.com/quickstart/server`,
  `https://docs.ag-ui.com/concepts/interrupts`
- Qwen3.8 serving guidance: `https://github.com/QwenLM/Qwen3.8`
- Harness references:
  `https://github.com/QwenLM/qwen-code`,
  `https://github.com/primeintellect-ai/prime-agent`,
  `https://github.com/NousResearch/hermes-agent`
