# Relational Schema

> Status: Draft v0.1. Defines the **Postgres 16** schema that durably mirrors the in-run `AgentState`
> (`state_schema.md` §18) and backs run history, provenance, and the API. ORM: SQLAlchemy 2 (async,
> psycopg3); migrations: Alembic (`storage/migrations/`). Implementation: `storage/models.py`,
> `storage/repositories.py`. Diagram: `documentation/diagrams/database_schema.mmd`. Large payloads go
> to the object store (`object_storage.md`), not here.

## 1. Purpose & scope

Maps each persisted `AgentState` substructure to a relational table, with keys, relationships, and
indexing. Defines DDL conventions (IDs, timestamps, JSONB, append-only enforcement). Does **not**
define provenance semantics (`provenance_model.md`) or the audit table internals
(`audit_log.md` — referenced here).

## 2. Entity overview

```
users ─< sessions ─< runs ─┬─< messages
                           ├─< subtasks ─< steps ─< evidence_items
                           ├─< artifacts ─(artifact_evidence)─ evidence_items
                           ├─< clarifications
                           ├─< review_items
                           └─< run_errors
macros (registry, referenced by runs.plan)        audit_log (see audit_log.md)
```

`run_id` is the universal FK. All child rows cascade-restrict (history is not deletable except via the
session-deletion path, `provenance_model.md` §8).

## 3. DDL conventions

- **Primary keys:** `id` = ULID/UUIDv7 stored as `uuid` (time-orderable, client-visible). No serial
  exposure.
- **Timestamps:** `created_at timestamptz NOT NULL DEFAULT now()`; domain times (e.g. `started_at`)
  stored as `timestamptz`. UTC everywhere.
- **Flexible payloads:** `jsonb` for structured-but-evolving shapes (params, inputs, summaries,
  confidence, provenance). Indexed with GIN where queried.
- **Enums:** Postgres enum types mirror `domain/enums.py` (`run_status`, `task_status`,
  `subtask_type`, `artifact_type`, `source_kind`, `review_decision`). Add values via migration.
- **Append-only tables** (`messages`, `steps`, `evidence_items`, `artifacts`, `run_errors`,
  `audit_log`): no `UPDATE`/`DELETE` in normal operation (enforced by repository layer + DB role
  grants; corrections insert new rows with `supersedes`). See `provenance_model.md` §8.
- **Soft references to blobs:** `*_ref` columns hold object-store keys (`object_storage.md`), never
  inline blobs.
- **Schema version:** `runs.schema_version` records the `AgentState` version for migration.

## 4. Tables

### `users`
`id`, `external_id` (auth subject), `display_name`, `role` (e.g. analyst, reviewer/PI — ties to
personas + review permissions, `human_review_policy.md` §10), `created_at`. Minimal in local-first
single-user deployments.

### `sessions` (workspaces)
Persistent typed workspace (`session_types.md`).
`id`, `user_id` → users, `type` (`variant_interpretation | genome_editing | strain_optimization | …`),
`title`, `defaults jsonb` (organism/assembly, review posture, model prefs), `memory jsonb` (carried
context), `created_at`, `updated_at`, `deleted_at` (nullable; session-level erasure).

### `runs`
`id`, `session_id` → sessions, `user_id`, `status run_status`, `schema_version`,
`intent jsonb`, `risk jsonb`, `plan jsonb` (kind, macro_id, rationale, revision),
`budget jsonb`, `final_report jsonb` (markdown + citation_map + confidence_summary + limitations +
followups), `normalized_inputs jsonb`, `created_at`, `started_at`, `finished_at`, `error jsonb`
(fatal only). Index: `(session_id, created_at)`, `status`.

### `messages` (append-only)
`id`, `run_id`, `role`, `content`, `artifact_ids uuid[]`, `evidence_ids uuid[]`, `step_id` (nullable),
`created_at`. Index: `(run_id, created_at)`.

### `subtasks`
`id`, `run_id`, `type subtask_type`, `capability`, `inputs jsonb`, `depends_on uuid[]`,
`status task_status`, `result_ref`, `is_actionable bool`, `created_at`, `updated_at`. Index:
`(run_id)`, `(run_id, status)`. (DAG edges live in `depends_on`.)

### `steps` (append-only)
Primitive ops / tool calls (`state_schema.md` §8) — the provenance + timeline unit.
`id`, `run_id`, `subtask_id` (nullable), `name`, `weight` (light|heavy), `tool`, `tool_version`,
`params jsonb`, `input_ref jsonb`, `input_hash`, `output_ref`, `output_hash`, `job_id` (async),
`status task_status`, `nondeterministic bool`, `seed`, `cache_hit bool`, `started_at`, `finished_at`,
`error`. Index: `(run_id, started_at)`, `(tool, tool_version, input_hash)` (cache lookup),
`subtask_id`.

### `evidence_items` (append-only)
`id`, `run_id`, `subtask_id`, `step_id`, `source`, `source_kind`, `claim`, `value jsonb`,
`confidence jsonb` (band/score/basis), `provenance jsonb` (tool/version/params/inputs/citations/
timestamp/hashes), `supersedes` (nullable self-FK), `created_at`. Index: `(run_id)`, `step_id`, GIN on
`provenance`.

### `artifacts`
Metadata only; heavy payload in object store.
`id`, `run_id`, `subtask_id`, `type artifact_type`, `title`, `storage_ref` (object key),
`storage_hash`, `summary jsonb` (inline preview/metadata), `actionable bool`, `created_at`. Link table
`artifact_evidence(artifact_id, evidence_id)`. Index: `(run_id)`, `type`.

### `clarifications`
`id`, `run_id`, `question`, `options jsonb` (id/label/value/is_recommended), `allow_multiple bool`,
`allow_freeform bool`, `blocking bool`, `answer jsonb` (selected_option_ids/freeform/answered_at),
`created_at`. Merge-by-id in state (`state_schema.md` §16).

### `review_items`
Actionable-biology gate (`human_review_policy.md`).
`id`, `run_id`, `subject_ref` (artifact/subtask), `reason`, `risks jsonb`, `evidence_ids uuid[]`,
`decision review_decision` (pending|approved|rejected), `note`, `decided_by` → users, `decided_at`,
`created_at`. Aggregate `ReviewState` is derived; decisions also mirrored to `audit_log`.

### `run_errors` (append-only)
`id`, `run_id`, `subtask_id`, `step_id`, `kind`, `message`, `recoverable bool`, `at`. Index: `run_id`.

### `macros` (registry)
Stored recipes referenced by `runs.plan.macro_id` (`routing_policy.md`, `state_schema.md` §6).
`id`, `key` (unique, human-readable), `version`, `definition jsonb` (subtask template + depends_on
DAG + defaults), `enabled bool`, `created_at`. Versioned; runs pin the macro `version` used.

### `audit_log`
Append-only consequential-event trail — schema in `audit_log.md`.

## 5. Run-state checkpointing vs history

- **In-run** state is checkpointed by the **LangGraph checkpointer** (Redis or Postgres) to enable
  durable pauses/resume (`control-flow/pause_and_resume.md`) and crash recovery. This is ephemeral
  working state keyed by `(run_id, checkpoint_id)`.
- **History** (the tables above) is the durable, queryable record written as the run progresses and
  finalized at completion. The checkpointer is an implementation detail; these tables are the
  contract. `run_id` joins both.

## 6. Indexing & query patterns (primary)

- Load a run for the UI: `runs` + children by `run_id` (run inspector, `workspace_interface.md`).
- Session history list: `runs (session_id, created_at desc)`.
- Tool-call timeline: `steps (run_id, started_at)`.
- Deterministic cache probe: `steps (tool, tool_version, input_hash)`.
- Evidence/provenance audit: `evidence_items` GIN(`provenance`) + citations.

## 7. Migrations

- Alembic, one revision per schema change; never edit a shipped migration. New enum values and columns
  are additive/back-compatible (mirrors `state_schema.md` migration policy §3). CI runs migrations on a
  scratch DB.

## 8. Requirements (testable)

- **RS-1** Every child row has a valid `run_id` FK; deleting a run is only possible via the
  session-deletion path and cascades (or is blocked) per `provenance_model.md` §8.
- **RS-2** Append-only tables reject in-place `UPDATE`/`DELETE` in normal operation (role grants +
  repository enforcement); corrections insert with `supersedes`.
- **RS-3** Round-trip: persisting an `AgentState` and reloading reconstructs an equivalent state
  (`tests/`), with `run_id` as the join key.
- **RS-4** Enum columns stay in sync with `domain/enums.py` (CI check).
- **RS-5** Heavy payloads are never stored inline; artifact/step payload columns hold object keys only.

## 9. Related specs

`state_schema.md` (§6–§18) · `provenance_model.md` · `object_storage.md` · `audit_log.md` ·
`session_types.md` · `routing_policy.md` · `human_review_policy.md` ·
`specs/interface/api_contracts.md` · `documentation/diagrams/database_schema.mmd`.
