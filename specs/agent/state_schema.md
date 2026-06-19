# Agent State Schema

> Status: Draft v0.1 — **keystone contract**. Defines the shared state object that flows through the
> LangGraph agent and the run/event shapes the API and frontend consume. The UI specs
> (`specs/interface/*`), API contract (`api_contracts.md`), data model (`specs/data/*`), and the
> other agent specs all derive from this document. Implementation lives in
> `src/backend/cellxp/agent/state.py`; when code and this spec diverge, reconcile here
> first (ADR-0004).

## 1. Purpose & scope

This spec defines:
1. the **`AgentState`** object passed between graph nodes (the in-run working memory),
2. the **substructures** it contains (inputs, entities, plan, steps, evidence, artifacts, review,
   errors),
3. the **reducers** (how concurrent/streamed updates merge), and
4. how the **task taxonomy** (steps / atomic / macro / composed; `task_patterns.md` §0) is
   represented in state.

It does **not** define node behavior (`graph_spec.md`), routing rules (`routing_policy.md`), model
selection (`tool_use_policy.md`), or persistence DDL (`specs/data/relational_schema.md`) — those
reference the shapes defined here.

## 2. Design principles

- **One source of truth per run.** All node outputs are reductions into `AgentState`; nothing
  important lives only in a node's local scope.
- **Append-only where it aids provenance.** Evidence, artifacts, steps, and errors accumulate
  (LangGraph `Annotated[..., add]` reducers) so the trace is complete and reproducible (`FR-24`).
- **Everything addressable.** Runs, messages, subtasks, steps, evidence, and artifacts carry stable
  IDs so the UI can deep-link and the trace can be reconstructed.
- **Serializable & versioned.** State is JSON-serializable (Pydantic v2 models / TypedDicts) and
  carries a `schema_version` for migration.
- **Coordinates & organism are explicit.** Any entity with genomic position carries organism +
  assembly + coordinate convention (never implicit; see `coordinate_systems.md`).

## 3. Current implementation (baseline)

The shipped scaffold (`agent/state.py`) is intentionally minimal:

```python
class AgentState(TypedDict, total=False):
    messages: Annotated[list[Any], add]
    user_query: str
    intent: str
    subtasks: list[dict[str, Any]]
    evidence: Annotated[list[dict[str, Any]], add]
    artifacts: Annotated[list[dict[str, Any]], add]
    final_report: str
```

This spec **extends** that shape (additive, back-compatible) to the target below. Migration: new keys
are optional (`total=False`); existing keys keep their meaning; `subtasks` gains structure (§6);
loose `dict` entries become typed models (§5, §8, §9).

## 4. Target `AgentState` (overview)

```python
class AgentState(TypedDict, total=False):
    # identity & meta
    schema_version: str                                   # e.g. "1.0"
    run_id: str                                           # stable run identifier
    created_at: str                                       # ISO-8601

    # conversation
    messages: Annotated[list[Message], add]               # full chat transcript (reduced)
    user_query: str                                       # latest user turn (convenience)

    # inputs (raw → normalized)
    raw_inputs: list[RawInput]                            # text, files, pasted sequences
    normalized_inputs: NormalizedInputs                   # parsed/validated inputs (§7)

    # understanding
    intent: Intent                                        # classified intent (§routing_policy)
    risk: RiskAssessment                                  # safety classification (§safety_model)
    entities: list[Entity]                                # resolved bio entities (§7)
    clarifications: list[Clarification]                   # open/answered questions to user

    # plan & execution
    plan: Plan                                            # the chosen plan (§6)
    subtasks: list[Subtask]                               # decomposed work units (§6)
    steps: Annotated[list[Step], add]                     # primitive ops executed (§8)
    cursor: ExecutionCursor                               # where we are in the plan

    # outputs
    evidence: Annotated[list[EvidenceItem], add]          # accumulated evidence (§9)
    artifacts: Annotated[list[ArtifactRef], add]          # accumulated artifacts (§10)
    final_report: Report                                  # synthesized answer (§11)

    # control
    review: ReviewState                                   # human-review gate (§12)
    errors: Annotated[list[RunError], add]                # non-fatal failures (§13)
    status: RunStatus                                     # lifecycle (§14)
    budget: Budget                                        # token/time/cost ceilings (§15)
```

Each substructure is specified below. Types are Pydantic v2 models unless noted; all are
JSON-serializable. Enums are defined in `domain/enums.py`.

## 5. Conversation: `Message`

```python
class Message(BaseModel):
    id: str
    role: Literal["user", "assistant", "system", "tool"]
    content: str                                  # markdown for assistant; raw for user
    created_at: str
    # assistant turns may reference produced artifacts / cited evidence
    artifact_ids: list[str] = []
    evidence_ids: list[str] = []
    # tool messages summarize a step (see §8) for the timeline
    step_id: str | None = None
```

`messages` is the canonical transcript; `user_query` mirrors the latest user message for node
convenience. Reducer: append (`add`).

## 6. Plan, subtasks & the task taxonomy

The taxonomy from `task_patterns.md` §0 is represented explicitly so the planner/router and UI can
reason about *how much was planned*.

```python
class Plan(BaseModel):
    id: str
    kind: Literal["atomic", "macro", "composed"]  # task taxonomy (task_patterns.md §0)
    macro_id: str | None = None                   # set when kind == "macro"
    rationale: str | None = None                  # planner's brief justification
    created_by: Literal["router", "planner", "macro", "user"]
    revision: int = 0                             # planner may revise mid-run

class Subtask(BaseModel):
    id: str
    type: SubtaskType                             # variant_effect | gwas | crispr | ... (enums)
    capability: str                              # FR ref / capability key
    inputs: dict[str, Any]                        # references into normalized_inputs/entities
    depends_on: list[str] = []                    # subtask IDs (DAG; enables composition/loops)
    status: TaskStatus                            # pending|running|done|failed|skipped|needs_review
    result_ref: str | None = None                # pointer to evidence/artifact produced
    is_actionable: bool = False                   # triggers review gate (§12)
```

- **Atomic** plan: one `Subtask` with a fixed internal step pipeline.
- **Macro** plan: `kind="macro"`, `macro_id` set; `subtasks` are the macro's pre-baked recipe
  (`depends_on` encodes the fixed order).
- **Composed** plan: a `Subtask` DAG the planner builds dynamically; `depends_on` may form chains and
  the planner can add subtasks across revisions (loops, e.g. inverse design).

`cursor` tracks progress:

```python
class ExecutionCursor(BaseModel):
    active_subtask_id: str | None = None
    completed: list[str] = []                     # subtask IDs
    remaining: list[str] = []
```

### Macro reference (registry)

A macro is a stored recipe; `state.plan.macro_id` references it. The macro *definition* schema
(registry entry) is owned by `routing_policy.md` + `specs/data/relational_schema.md`; in-state we
only carry the `macro_id`, `revision`, and the expanded `subtasks`.

## 7. Inputs & entities

```python
class RawInput(BaseModel):
    id: str
    kind: Literal["text", "file", "sequence", "variant", "interval", "identifier"]
    value: str | None = None                      # inline value (text/sequence/id)
    file_ref: str | None = None                   # object-store key for uploads
    mime: str | None = None

class NormalizedInputs(BaseModel):
    organism: str | None = None                   # required before coordinate ops (FR-11)
    assembly: str | None = None
    sequences: list[SequenceInput] = []
    variants: list[Variant] = []                  # domain/models.py
    intervals: list[GenomicInterval] = []         # domain/models.py
    identifiers: list[str] = []                    # rsIDs, gene symbols, accessions
    warnings: list[str] = []                       # normalization notes

class Entity(BaseModel):
    id: str
    type: Literal["gene", "variant", "interval", "protein", "metabolite",
                  "transcript", "regulatory_element", "organism", "pathway"]
    label: str
    resolved: bool                                # False → needs clarification
    organism: str | None = None
    assembly: str | None = None
    refs: dict[str, str] = {}                      # cross-DB IDs (Ensembl, UniProt, …)
    ambiguity: list[str] = []                      # candidate resolutions if unresolved
```

`Variant`, `GenomicInterval`, and `SequenceInput` reuse/extend `domain/models.py`. Any positioned
entity MUST carry organism + assembly (`coordinate_systems.md`).

```python
class ClarificationOption(BaseModel):
    id: str
    label: str                                    # shown to the user
    value: str | None = None                      # canonical value applied if chosen
    is_recommended: bool = False                  # surfaced first / highlighted

class Clarification(BaseModel):
    id: str
    question: str
    options: list[ClarificationOption] = []       # Claude-Code-style choices
    allow_multiple: bool = False                  # user may select >1 option
    allow_freeform: bool = True                   # "Other" / "yes, and …" free-text addition
    blocking: bool = True                          # halts dependent subtasks until answered
    answer: ClarificationAnswer | None = None      # filled when user responds

class ClarificationAnswer(BaseModel):
    selected_option_ids: list[str] = []           # chosen option id(s)
    freeform: str | None = None                   # the "and …" addition or "Other" text
    answered_at: str | None = None
```

The interactive presentation of a `Clarification` (option cards, recommended option, multi-select,
the "yes, and …" free-text affordance) is specified in
`specs/interface/streaming_protocol.md` §7. `allow_freeform=True` is what enables a user to accept an
option **and** add extra guidance in the same turn.

## 8. Steps (primitive operations)

The building-block layer (`task_patterns.md` §0.1). Every tool/model/data/transform call is recorded
as a `Step` for provenance and the UI tool-call timeline.

```python
class Step(BaseModel):
    id: str
    subtask_id: str | None = None
    name: str                                     # e.g. "extract_coordinates", "call_alphagenome"
    weight: Literal["light", "heavy"]             # heavy → async job
    tool: str | None = None                       # service/model identity (catalog key)
    tool_version: str | None = None               # provenance (FR-24)
    params: dict[str, Any] = {}
    input_ref: dict[str, Any] = {}                # normalized inputs used
    output_ref: str | None = None                # pointer to evidence/artifact/object-store
    job_id: str | None = None                     # for async heavy steps (jobs/queues)
    status: TaskStatus
    started_at: str | None = None
    finished_at: str | None = None
    error: str | None = None
```

Reducer: append. Steps are the unit the run inspector and the chat tool-call timeline render
(`specs/interface/*`).

## 9. Evidence

Extends `domain/models.py: EvidenceItem` into a typed, addressable record.

```python
class EvidenceItem(BaseModel):
    id: str
    source: str                                   # model/tool/db name
    source_kind: Literal["model", "database", "literature", "computation"]
    claim: str                                    # the assertion this supports
    value: Any | None = None                      # structured payload (deltas, scores, rows)
    confidence: Confidence                        # calibrated value or qualitative band (§ref)
    provenance: Provenance                        # versions, params, inputs, citations
    subtask_id: str | None = None
    step_id: str | None = None

class Confidence(BaseModel):
    band: Literal["high", "medium", "low", "unknown"]
    score: float | None = None                    # 0..1 when calibrated
    basis: str | None = None                      # what the confidence is based on

class Provenance(BaseModel):
    tool: str | None = None
    tool_version: str | None = None
    params: dict[str, Any] = {}
    inputs: dict[str, Any] = {}
    citations: list[str] = []                      # DOIs/PMIDs/URLs/db accessions
    timestamp: str | None = None
```

Confidence/provenance semantics are defined in `documentation/explanation/evidence_and_confidence.md`
and consumed by `evidence_integration.md`. Reducer: append.

## 10. Artifacts (in-state references)

State carries lightweight **references**; the full artifact model (taxonomy, payload schema,
rendering) is `specs/interface/artifact_model.md`.

```python
class ArtifactRef(BaseModel):
    id: str
    type: ArtifactType                            # genome_track | locus_plot | structure_3d |
                                                  # contact_map | guide_table | origami | report | ...
    title: str
    subtask_id: str | None = None
    storage_ref: str | None = None               # object-store key for heavy payloads
    summary: dict[str, Any] = {}                  # small inline preview/metadata
    evidence_ids: list[str] = []
    actionable: bool = False                       # gated artifacts (e.g. guide table) (§12)
    created_at: str
```

Reducer: append.

## 11. Report (final synthesis)

```python
class Report(BaseModel):
    markdown: str                                 # the written answer with inline citations
    citation_map: dict[str, str] = {}             # citation marker → evidence_id
    artifact_ids: list[str] = []                  # featured artifacts
    confidence_summary: Confidence | None = None
    limitations: list[str] = []
    suggested_followups: list[str] = []           # agentic: proposed next steps/experiments
```

## 12. Human-review state (gate)

Drives the actionable-biology gate (`human_review_policy.md`, ADR-0005, `FR-25/26`).

```python
class ReviewState(BaseModel):
    required: bool = False                         # set when any actionable output is produced
    status: Literal["not_required", "pending", "approved", "rejected", "changes_requested"] \
        = "not_required"
    items: list[ReviewItem] = []
    decided_at: str | None = None

class ReviewItem(BaseModel):
    id: str
    subject_ref: str                              # artifact/subtask under review
    reason: str                                   # why it's actionable
    risks: list[str] = []
    evidence_ids: list[str] = []
    decision: Literal["pending", "approved", "rejected"] = "pending"
    note: str | None = None
```

The graph MUST NOT advance an actionable subtask to "recommended" output until its `ReviewItem` is
`approved`.

## 13. Errors

```python
class RunError(BaseModel):
    id: str
    subtask_id: str | None = None
    step_id: str | None = None
    kind: str                                     # see domain/errors.py
    message: str
    recoverable: bool                             # if True, run continues (partial results)
    at: str
```

Non-fatal errors accumulate (graceful degradation, `NFR-6`); a fatal error sets `status="failed"`.

## 14. Run lifecycle: `RunStatus` & `TaskStatus`

```
RunStatus:  queued → running → (awaiting_input | awaiting_review)? → running → completed | failed | cancelled
TaskStatus: pending → running → done | failed | skipped | needs_review
```

`awaiting_input` (open blocking `Clarification`) and `awaiting_review` (pending `ReviewState`) pause
the run and surface to the UI; both resume on user action.

## 15. Budget & limits

```python
class Budget(BaseModel):
    max_tokens: int | None = None
    max_wallclock_s: int | None = None
    max_cost_usd: float | None = None
    spent: dict[str, float] = {}                   # running totals
```

Used by the planner/router to bound composed/looping tasks (e.g. inverse-design iterations).

## 16. Reducers (concurrency semantics)

| Field | Reducer | Why |
|---|---|---|
| `messages`, `steps`, `evidence`, `artifacts`, `errors` | append (`Annotated[list, add]`) | accumulate full trace; subgraphs may emit concurrently |
| `subtasks`, `plan`, `cursor`, `review`, `status`, `intent`, `risk`, `normalized_inputs`, `final_report`, `budget` | last-write-wins (single owner node) | one node owns each at a time |
| `entities`, `clarifications` | merge-by-id | resolvers/UI update items incrementally |

Nodes that run in parallel MUST only write append/merge-by-id fields to avoid clobbering.

## 17. Streaming events (state → UI)

The API streams state deltas as typed SSE events. Most events map 1:1 to state mutations; a few
(`reasoning.*`, `intent.classified`, `activity.update`) are **presentational** — they convey progress
to the UI and are not necessarily durable state. The full streaming + presentation contract
(channels, the collapsible "thinking" surface, tool-call rendering, interactive clarifications) is
`specs/interface/streaming_protocol.md`; the wire/transport contract is `api_contracts.md`.

| Event | Maps to | Notes |
|---|---|---|
| `run.status` | `status` | lifecycle transitions (§14) |
| `reasoning.delta` | — (ephemeral) | streamed thinking tokens; rendered under a collapsible toggle |
| `reasoning.summary` | — (ephemeral) | short summary shown when thinking collapses |
| `intent.classified` | `intent` | surfaced as an activity chip |
| `plan.updated` | `plan`/`subtasks` | plan created/revised |
| `subtask.updated` | `subtasks[i]` | status/result changes |
| `step.started` / `step.finished` | `steps` (append) | tool-call timeline + tool I/O summaries |
| `activity.update` | — (ephemeral) | human-readable status line ("Calling AlphaGenome…") |
| `evidence.added` | `evidence` (append) | new evidence item |
| `artifact.added` / `artifact.updated` | `artifacts` (append) | visualization placeholder → populated |
| `message.delta` | `messages` (append) | assistant message tokens |
| `report.delta` | `final_report` | streamed final answer tokens |
| `clarification.requested` | `clarifications` | interactive question card (options + "yes, and") |
| `review.requested` | `review` | actionable-biology gate card |
| `error.added` | `errors` (append) | non-fatal error surfaced |
| `run.completed` | `status` | terminal |

Each event carries the affected object (or delta) and its IDs so the client can patch its local copy
without re-fetching. Reasoning/activity events are best-effort and MAY be dropped on reconnect;
state-backed events are replayable (`streaming_protocol.md` §9).

## 18. Persistence mapping

State is checkpointed by LangGraph during a run and persisted for history/reproducibility. The
relational mapping (runs, messages, subtasks, steps, evidence, artifacts, review, errors tables) and
which payloads go to object storage vs Postgres are defined in `specs/data/relational_schema.md`,
`specs/data/object_storage.md`, and `specs/data/provenance_model.md`. `run_id` is the join key.

## 19. Open questions

- Macro definition schema: fully here vs owned by `routing_policy.md`/data model? (currently: ref by
  `macro_id`, definition lives in the data model.)
- Granularity of `step` recording for very chatty tools (batch vs per-call).
- Whether `entities` should be a typed union per `type` or a single model with optional fields
  (currently single model).
- Multi-turn runs: does a follow-up question fork a new run or extend the existing `run_id`?

## 20. Related specs

`graph_spec.md` · `routing_policy.md` · `tool_use_policy.md` · `evidence_integration.md` ·
`human_review_policy.md` · `task_patterns.md` · `specs/interface/artifact_model.md` ·
`specs/interface/api_contracts.md` · `specs/interface/streaming_protocol.md` · `specs/data/*` ·
`coordinate_systems.md` · `evidence_and_confidence.md`.
