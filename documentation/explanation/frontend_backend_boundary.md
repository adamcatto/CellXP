# Frontend / Backend Boundary

> Long-form explainer for **where the line sits** between the Python FastAPI agent runtime
> backend and the TypeScript Next.js client (and, later, the native macOS shell). The
> normative wire is `specs/interface/api_contracts.md`; this document is the discipline that
> keeps the wire honest. Anchor decisions: `ADR-0004` (specs as contracts),
> `ADR-0001` (unified src/), `specs/serving/frontend_deployment.md`.

## 1. The principle in one sentence

**The backend owns all scientific truth and all consequential decisions; the client owns
presentation, interaction, and local UI state.** Anything that would be different on a
different client — color choices, dock layout, keyboard shortcuts, pane viewport — is the
client's job. Anything where a different client would give a different scientific answer —
coordinate transforms, evidence interpretation, review decisions, model selection — is the
backend's job, full stop.

## 2. What lives on each side

### Backend (Python, FastAPI + skill/policy runtime)

- **The agent runtime and canonical state.** Planning may live in a mature harness, but every
  capability invocation and consequential policy decision crosses typed skills and the CellXP
  kernel. The client sees only authorized typed events and durable state.
- **Every service** (variant effect, GWAS, CRISPR, structure, binding, annotation, RAG,
  visualization, origami) and their normalization logic.
- **Every coordinate transform.** Reference assembly, contig naming, strand handling,
  liftover, circular-genome handling — `specs/services/reference_genome_service.md`. The
  client never converts coordinates; it displays them.
- **Every artifact payload.** Genome tracks, structures, contact maps, tables, reports —
  the canonical scientific values live on the backend and stream as typed payloads
  (`specs/interface/artifact_model.md`).
- **Every safety/review decision.** Risk clearance and the actionable-review state machine are
  backend policy; the audit log is backend; the client *renders* a review card and *posts* a
  decision (`ADR-0005`, ADR-0008, `specs/agent/human_review_policy.md`).
- **Every provenance record.** Steps, evidence, audit entries, content hashes — all
  backend-owned, all append-only (`specs/data/provenance_model.md`).
- **Auth and authorization.** Every request is authorized at the FastAPI middleware against
  session ownership; the client carries credentials but the decision is the backend's
  (`specs/serving/agent_runtime_serving.md` §12).

### Client (TypeScript, Next.js)

- **Rendering.** Markdown to HTML, payload to Canvas/SVG/Mol\*, table virtualization, dock
  layout. The client is allowed to be opinionated about visuals as long as it doesn't
  change values.
- **Local interaction state.** Pan/zoom, hover, selection, sort/filter, sidebar collapse —
  all client-local, none persisted to the run trace (`PNS-9`, `WSP-6`).
- **The selection bus.** Cross-pane highlight events are workspace-scoped and ephemeral
  (`specs/interface/interactive_panes.md` §5). The backend doesn't know which pixel the
  user is hovering on.
- **Composer ergonomics.** Slash menus, `@`-mention autocompletes, drag-drop uploads,
  paste-detection. The composer *requests* resolution from the backend (entity lookup,
  paste classification suggestion); the *decision* of what to send is the user's, expressed
  through the client.
- **Streaming consumption.** The client subscribes to SSE, patches its local state per
  event, renders incrementally, reconnects with `Last-Event-ID` (`specs/interface/streaming_protocol.md`).
- **Native shells.** A future macOS app re-implements rendering on native primitives but
  consumes the same wire (`specs/serving/frontend_deployment.md` §6).

## 3. What never lives in the client

The negative list is the load-bearing one. The client MUST NOT contain code that:

- Converts coordinates (e.g. 1-based → 0-based, GRCh37 → GRCh38). Even for display, the
  conversion is the backend's call and the convention is in the payload.
- Decides which model to call (ESMFold vs Boltz, AlphaGenome vs Evo 2). The harness selects an
  authorized skill and the backend validates applicability; the client surfaces the choice.
- Decides whether something is actionable. The backend marks
  `ArtifactRef.actionable=true`; the client renders the consequence.
- Approves or auto-approves a review. The user clicks Approve; the audit-log entry and
  state transition are backend (`api_contracts.md` §6).
- Constructs a candidate artifact directly. Editor panes send an edit request; the backend
  produces the candidate (`interactive_panes.md` §6).
- Interprets evidence. Citation rendering is fine; deciding "this citation supports this
  claim" is not — that is the backend evidence/report workflow.
- Validates biological inputs (ref allele, organism/assembly compatibility, edit-spec
  feasibility). Client-side checks for malformed *strings* are fine; checks against
  biological reality MUST round-trip the backend.
- Embeds any API key for a model, vector index, or external service.

If a feature feels like it would be quicker to write in the client because "we already have
the data on hand" — that's the moment to write it on the backend instead. The data is on
hand for a reason.

## 4. The wire (canonical REST/SSE + AG-UI projection)

The boundary's machine-readable form is **OpenAPI 3.1**, generated from FastAPI and
versioned (`specs/interface/api_contracts.md`). Concretely:

- **REST** for durable resources: sessions, runs, artifacts, reviews, uploads, exports.
- **SSE** for ordered run events: thinking, activity, message/report deltas, artifact
  added/updated, clarification/review cards, lifecycle.
- **AG-UI** as the browser-agent projection consumed through the same-origin CopilotKit runtime; it
  maps to canonical runs/events and does not become a second scientific store (ADR-0006).
- **Multipart** for uploads: streamed to object storage, content-hashed, returned as
  `UploadRef` (`api_contracts.md` §4).
- **`application/problem+json`** for errors, with stable codes and no leakage of secrets,
  prompts, stack traces, or object keys (`api_contracts.md` §2).
- **Idempotency keys** on mutating endpoints, including run creation (`api_contracts.md` §2,
  §5).
- **Optimistic-concurrency revisions** on update endpoints (e.g. session settings,
  `api_contracts.md` §3).

Everything else flows from these primitives. There is no GraphQL, no WebSocket, no separate admin
API. REST remains the durable channel; SSE/AG-UI are projections of canonical ordered events.

## 5. Generated client and the portability contract

The TypeScript client (`src/frontend/lib/api.ts`) is **generated** from the FastAPI OpenAPI
document. The build fails on drift between the served schema and the generated types
(`API-9`). This is the load-bearing mechanism for "the client never invents shapes":

- Adding a field is additive; the client picks it up on regen.
- Renaming a field requires a coordinated change to both sides in one PR.
- Removing or changing a field's semantics is a major-version API change; clients in the
  wild keep working until they're upgraded.

The same mechanism is what makes the **native macOS shell** portable. The Swift / Tauri
client consumes the same OpenAPI document (or its JSON fixtures) and the same SSE event
shapes. No scientific logic was added to the web client for it to leak into the native
shell — the wire is the contract (`api_contracts.md` §10, `serving/frontend_deployment.md` §6).

## 6. Streaming, latency, and progressive disclosure

The split also reflects a UX bet: live progress is a function of the backend, not the
client. The backend emits events as state changes; the client renders. This puts the
streaming UX in one place and means a CLI / native / scriptable client gets the same live
behavior for free, by subscribing to the same SSE.

This is why the streaming protocol (`specs/interface/streaming_protocol.md`) is a backend
spec. Concretely:

- The "Thinking" disclosure, the activity log, the progressive artifact bubbles, and the
  clarification/review cards are all **events**, not client-side fictions.
- The client's job is to make these legible: collapsing, grouping, scrolling, accessibility
  live regions. None of that requires the client to invent scientific narrative.

## 7. Authentication, privacy, and consent gates

The boundary is also where privacy lives:

- **Auth** is enforced at the backend middleware. The client carries credentials but never
  *decides* access.
- **Hosted-provider use** (LLM or other) is a backend configuration; the client *surfaces*
  the consent gate (a chip in the assistant turn footer, a one-time confirmation on
  sensitive paste) before the backend egresses private content
  (`specs/interface/chat_interface.md` §11, `specs/services/llm_service.md` §8).
- **Logs and notifications** never carry raw biological payloads, only IDs and bounded
  summaries (`API-9`, `WSP-9`).
- **Object access** is via short-lived signed URLs the backend issues per-request; the
  client never sees raw bucket keys (`specs/data/object_storage.md` §5).

## 8. Common temptations (and the right response)

- *"The user wants to coerce coordinates; we have a JS helper."* — Send the coordinates to
  the backend; it converts and records the transform in provenance.
- *"We can save a round-trip if the client computes X."* — If X has scientific meaning, the
  round-trip is the feature.
- *"This validation is just a regex on a sequence."* — Mirror the regex on the client for
  immediate feedback; the authoritative validation still runs on the backend before
  dispatch.
- *"Let's let the user mark a guide approved from the table; it's faster."* — Approval is
  a structural decision with an audit-log entry. Surface a clear approval affordance, post
  to the API, render the result. Don't shortcut.
- *"We need a quick prototype; ship it client-only first."* — Prototype on the backend with
  a thin client; if the prototype graduates, you don't have to rewrite the science.

## 9. Where to go from here

- **Normative wire spec:** `specs/interface/api_contracts.md`.
- **Streaming UX:** `specs/interface/streaming_protocol.md`.
- **Artifact model:** `specs/interface/artifact_model.md` (the schema-shape of everything
  rendered).
- **Pane and workspace UX:** `specs/interface/interactive_panes.md`,
  `specs/interface/workspace_interface.md`.
- **Frontend deployment + native portability:** `specs/serving/frontend_deployment.md`.
- **Specs-as-contracts discipline:** `ADR-0004`.
