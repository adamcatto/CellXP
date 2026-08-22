# API Contracts

> Status: Draft v0.1. Normative HTTP and SSE boundary between the FastAPI backend and CellXP
> clients. State shapes derive from `specs/agent/state_schema.md`; session shapes from
> `specs/agent/session_types.md`; artifact shapes from `specs/interface/artifact_model.md`; event
> semantics from `specs/interface/streaming_protocol.md`. Base path: `/api/v1`.

## 1. Goals and Conventions

The API supports a TypeScript web client first and later native clients without exposing LangGraph,
database, or object-store internals. It uses JSON REST resources for durable state, SSE for ordered
run events, and multipart uploads for files.

The web client additionally uses `POST /ag-ui`, an AG-UI protocol adapter consumed through the
same-origin Next.js CopilotKit runtime. This endpoint maps to the resources below; it is not a second
system of record. The canonical REST/SSE API remains available to every client (ADR-0006).

- JSON fields use `snake_case`; timestamps are UTC ISO-8601; IDs are opaque UUIDv7/ULID strings.
- All responses include `X-Request-ID`; mutating requests accept `Idempotency-Key`.
- API schemas are generated as OpenAPI 3.1 and are the source for a checked-in/generated TypeScript
  client and portable JSON schema fixtures.
- Paths are versioned. Additive fields and enum values are non-breaking; removals, semantic changes,
  and newly required fields require a new major API version.
- Clients MUST ignore unknown additive fields/events and MUST NOT depend on database row shapes.

## 2. Common Envelopes

Successful single-resource responses return the resource directly. Collections use:

```json
{"items": [], "next_cursor": null}
```

Errors use `application/problem+json`:

```json
{
  "type": "https://cellxp.local/problems/validation",
  "title": "Input validation failed",
  "status": 422,
  "detail": "Assembly is required for positioned inputs.",
  "instance": "/api/v1/runs/run_01...",
  "request_id": "req_01...",
  "code": "assembly_required",
  "errors": [{"path": "normalized_inputs.assembly", "message": "Required"}]
}
```

Known status usage: `400` malformed request, `401/403` authentication/authorization, `404` absent or
not visible, `409` lifecycle/revision conflict, `413` upload too large, `422` semantic validation,
`429` capacity/budget limit, `503` dependency unavailable. Errors never include secrets, raw prompts,
stack traces, object keys, or inaccessible-resource existence.

Cursor pagination is stable by `(created_at, id)`. List endpoints accept `limit` (default 50, max
200) and opaque `cursor`. Filters are endpoint-specific and server validated.

## 3. Sessions / Workspaces

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/sessions` | create typed workspace |
| `GET` | `/sessions` | list visible workspaces |
| `GET` | `/sessions/{session_id}` | fetch session summary/defaults |
| `PATCH` | `/sessions/{session_id}` | update title/defaults/pins with revision guard |
| `DELETE` | `/sessions/{session_id}` | request audited session erasure |
| `GET` | `/sessions/{session_id}/runs` | session-scoped run history |
| `GET` | `/sessions/{session_id}/artifacts` | session artifact library |
| `GET` | `/sessions/{session_id}/files` | workspace file manifest |

Creation accepts `type`, `title`, optional organism/assembly/persona, and optional inferred defaults.
Updates include `expected_revision`; stale writes return `409 revision_conflict`. Changing a session
default affects future runs only and never rewrites persisted run inputs.

## 4. Uploads and Inputs

`POST /sessions/{session_id}/uploads` accepts multipart data plus declared input kind. The backend
streams bytes to object storage, computes a content hash, validates configured size/media limits,
and returns an `UploadRef`:

```python
class UploadRef(BaseModel):
    id: str
    filename: str
    media_type: str
    size: int
    content_hash: str
    status: Literal["uploaded", "scanning", "ready", "rejected"]
    input_kind: str | None = None
```

Uploads are private to the session. Filenames are display metadata, never filesystem paths. Parsing
or biological validation occurs as a recorded run step; upload success does not imply valid FASTA,
VCF, PDB/mmCIF, molecule, or origami content.

## 5. Runs and Messages

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/sessions/{session_id}/runs` | submit one user turn and start a run |
| `GET` | `/runs/{run_id}` | fetch durable run snapshot |
| `GET` | `/runs/{run_id}/events` | open/resume SSE stream |
| `POST` | `/runs/{run_id}/cancel` | request cooperative cancellation |
| `POST` | `/runs/{run_id}/reproduce` | create a run from recorded inputs/versions |
| `GET` | `/runs/{run_id}/steps` | paginated execution trace |
| `GET` | `/runs/{run_id}/evidence` | paginated evidence records |
| `GET` | `/runs/{run_id}/audit` | hash-chain-verified consequential audit records |

Run creation:

```python
class CreateRunRequest(BaseModel):
    message: str | None = None
    inputs: list[RawInput] = []                  # may reference UploadRef ids
    overrides: RunOverrides | None = None        # organism/assembly/model/budget, run-scoped
    referenced_artifact_ids: list[str] = []
    client_request_id: str                       # client-generated dedupe key

class CreateRunResponse(BaseModel):
    run_id: str
    session_id: str
    status: RunStatus
    stream_url: str
    created_at: str
```

At least one of `message` or `inputs` is required. Referenced artifacts MUST belong to the same
authorized workspace unless an explicit copy/import operation has occurred. A duplicate
`client_request_id` within a session returns the original run rather than dispatching twice.
The endpoint commits the queued run and one durable `run.status=queued` event, enqueues an
idempotent graph-executor command, and returns `202` without executing LangGraph in the API process.
Queue unavailability returns `503`; a committed run that could not be enqueued remains recoverable
by the command outbox/reconciler and MUST NOT be dispatched twice.

The run snapshot is a durable, bounded representation of `AgentState`: message/report text,
normalized metadata, plan/subtasks, compact step/evidence/artifact summaries, pending interactions,
status, and errors. Large tool output and artifacts are fetched through dedicated endpoints.

Cancellation is idempotent. Completed/failed runs remain terminal; cancelling them returns current
state. Reproduction creates a new run linked by `reproduces_run_id`; it never mutates the source run.

## 6. Pause, Clarification, and Review

| Method | Path | Request |
|---|---|---|
| `POST` | `/runs/{run_id}/clarifications/{clarification_id}/answer` | `ClarificationAnswer` |
| `POST` | `/runs/{run_id}/reviews/{review_item_id}/decision` | `ReviewDecisionRequest` |

```python
class ReviewDecisionRequest(BaseModel):
    decision: Literal["approve", "reject", "request_changes"]
    note: str | None = None
    expected_run_status: Literal["awaiting_review"]
```

Answers/decisions are idempotent by request key and accepted only for the currently pending item.
Conflicting second decisions return `409`. The API records actor, timestamp, request ID, and note in
the audit log before resuming the graph. Approval is per item, not blanket approval for later output.

## 7. Artifacts, Content, and Exports

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/artifacts/{artifact_id}` | fetch `ArtifactManifest` |
| `GET` | `/artifacts/{artifact_id}/content` | stream inline/object payload with authorization |
| `GET` | `/artifacts/{artifact_id}/tiles` | bounded range/tile request for supported types |
| `GET` | `/artifacts/{artifact_id}/guide-pools` | list persisted ordered CRISPR candidate pools |
| `POST` | `/artifacts/{artifact_id}/guide-pools` | persist a new ordered CRISPR candidate pool |
| `PUT` | `/artifacts/{artifact_id}/guide-pools/{pool_id}` | replace pool membership using `expected_revision` |
| `POST` | `/artifacts/{artifact_id}/exports` | create or resolve requested export |
| `GET` | `/artifacts/{artifact_id}/exports/{export_id}` | status/download descriptor |

Content responses use the declared media type, immutable `ETag=content_hash`, range requests where
supported, and `Content-Disposition` with a sanitized filename. Short-lived signed URLs MAY be
returned, but raw object-store keys and permanent public URLs MUST NOT be exposed.

Export creation accepts `format`, optional renderer-independent view state (viewport, visible tracks,
selection), dimensions, and coordinate convention. It records the source artifact revision and
transform parameters. Actionable export restrictions follow `artifact_model.md` §8.
An actionable export returns `409` until approval. A successful export persists its descriptor,
stores immutable content through the configured object store, and appends a linked
`side_effect.performed` audit record. Manifest responses never expose object-store keys.

Guide pools contain ordered candidate IDs and retain the source guide-table artifact ID. Updates
use optimistic concurrency; a stale `expected_revision` returns `409`. Persisting a candidate pool
does not approve it or bypass the source artifact's review state.

## 8. SSE Wire Contract

`GET /runs/{run_id}/events` returns `text/event-stream`, disables intermediary buffering/caching,
and accepts `Last-Event-ID` for replay. Each frame uses the event type for `event`, monotonic sequence
for `id`, and a JSON envelope for `data`:

```text
id: 42
event: artifact.updated
data: {"schema_version":"1.0","run_id":"run_...","seq":42,"at":"...","data":{...}}

```

```python
class RunEvent(BaseModel):
    schema_version: str
    run_id: str
    seq: int
    at: str
    data: dict[str, Any]
```

State-backed events are retained/replayable for the configured run-retention window. Ephemeral
`reasoning.*` and `activity.update` events may not replay; a snapshot plus later durable events MUST
still reconstruct the user-visible run. The server sends SSE comment heartbeats at least every 15 s
during silence. A slow client may lose ephemeral updates but not durable state; if replay is no longer
available the server emits `stream.reset` containing a snapshot URL and next sequence.

Streams close after a terminal lifecycle event. Network closure does not cancel a run. Multiple
read-only stream consumers are allowed and receive the same ordered durable events.

### 8.1 AG-UI adapter

`POST /ag-ui` accepts AG-UI `RunAgentInput` and returns the protocol's encoded event stream. AG-UI's
published camelCase wire schema is an intentional exception to CellXP JSON naming. The adapter:

- maps `threadId` to an authorized CellXP `session_id`;
- maps each new user turn to idempotent run creation and retains the canonical CellXP `run_id` in
  the bounded state projection;
- emits lifecycle, answer, tool-call, state, and interrupt events from canonical run state/events;
- represents artifacts by reference and never embeds large payloads;
- maps `resume[]` entries to the matching pending clarification/review on the same session and
  resumes only through the existing checkpoint/audit path;
- emits state/messages needed for resume before an interrupt outcome;
- treats AG-UI disconnect as read-side disconnect, not cancellation.

The Next.js CopilotKit runtime is an auth/context broker only. It MUST NOT run scientific
transformations, decide review outcomes, or persist an independent authoritative run.

## 9. Authentication, Privacy, and Cross-Origin Use

Local single-user mode may use loopback-bound session authentication, but the API still enforces
session ownership and CSRF/origin rules. Multi-user deployments require authenticated principals and
authorization on every session/run/artifact/object request. CORS is deny-by-default and explicitly
configured for the web or native-app origin.

Sequence inputs, uploads, prompts, and artifacts are private. Logs use IDs and bounded summaries,
not raw biological payloads. Remote-provider use is surfaced in run metadata before private content
is sent off-host.

## 10. Type Generation and Client Portability

FastAPI's OpenAPI document is validated in CI. The web app generates TypeScript request/response
types and a thin transport client from it; application state uses domain interfaces independent of
React/Next.js. A future macOS client consumes the same REST/SSE contracts and JSON fixtures. No
scientific transformation, coordinate conversion, or review decision logic may exist only in a
platform UI client.

## 11. Requirements

- **API-1** All durable resources and errors MUST have versioned, machine-readable schemas published
  through OpenAPI 3.1.
- **API-2** Mutating endpoints MUST support idempotency; revision-sensitive updates MUST reject stale
  writes.
- **API-3** Every request MUST be authorized against the owning session; inaccessible resources MUST
  not leak existence or raw object keys.
- **API-4** Run events MUST be ordered by monotonic sequence, resume via `Last-Event-ID`, and preserve
  durable state across reconnects.
- **API-5** Stream disconnection MUST NOT cancel a run; cancellation requires the explicit endpoint.
- **API-6** Heavy payloads MUST be fetched through content/tile endpoints, not embedded in run
  snapshots or SSE.
- **API-7** Clarification answers and review decisions MUST be audit logged before graph resumption.
- **API-8** Uploaded bytes MUST be streamed, size-limited, content-hashed, private, and treated as
  untrusted.
- **API-9** API and generated TypeScript client compatibility MUST be covered by schema/contract tests.
- **API-10** Errors MUST be actionable and safe, with stable codes and no secrets/raw stack traces.
- **API-11** Run start/resume/cancel endpoints MUST return without executing graph or heavy domain
  work inline; production execution is performed by Redis-backed workers.
- **API-12** Actionable exports MUST fail closed until approval and MUST link the export to the
  persisted review and hash-chain-verified audit trail.
- **API-13** The AG-UI adapter MUST preserve canonical session/run/artifact IDs, authorization,
  idempotency, payload-size limits, and graph-enforced interrupt semantics; frontend tools MUST NOT
  become an alternate execution or approval path.

## 12. Related

`specs/interface/streaming_protocol.md` · `specs/interface/artifact_model.md` ·
`specs/interface/workspace_interface.md` · `specs/agent/control-flow/pause_and_resume.md` ·
`specs/data/object_storage.md` · `specs/data/audit_log.md`.
