# Data Layer Specs

The **persistence substrate** for CellXP: how runs, evidence, artifacts, and provenance
are durably stored, addressed, and reproduced. These specs make the in-run `AgentState`
(`specs/agent/state_schema.md`) durable and auditable, and define the contracts the services
(`specs/services/*`) and API (`specs/interface/api_contracts.md`) read/write.

## Read in this order

| Spec | Defines | Why it's first/last |
|---|---|---|
| `provenance_model.md` | **keystone** — what we capture to reproduce & audit any claim/artifact; identity, versioning, content addressing, immutability | everything else references it |
| `relational_schema.md` | Postgres tables (runs, messages, subtasks, steps, evidence, artifacts, review, errors, sessions, macros, users) + DDL conventions, migrations | the durable mirror of `state_schema.md` §18 |
| `object_storage.md` | what goes to the object store vs Postgres; key scheme, content addressing, retention, pluggable backend | heavy artifact payloads |
| `vector_index.md` | RAG embeddings + chunk store; chunk schema, namespaces, provenance link | grounds the `rag` capability |
| `audit_log.md` | append-only record of consequential events (review decisions, refusals, side effects) | safety/compliance trail |

## Shared conventions

- **`run_id` is the universal join key.** Every persisted row traces to a run (and, where relevant, a
  `session_id`). IDs are stable and client-visible for deep-linking (`state_schema.md` §2).
- **Append-only where provenance demands it.** Messages, steps, evidence, artifacts, errors, and
  audit entries are **insert-only**; corrections are new rows, never destructive edits (`FR-24`).
- **Two tiers of storage.** Small/queryable/structured → **Postgres** (JSONB for flexible payloads);
  large/binary/opaque → **object store**, referenced by key. Embeddings → **vector index**. Rule of
  thumb + size threshold in `object_storage.md` §3.
- **Provenance is non-optional.** No substantive evidence/artifact persists without a `Provenance`
  record (`provenance_model.md`; ≥95% completeness target, `success_metrics.md` D2).
- **Pluggable backends.** Object store and vector index are interface-first (`file://`/local dev →
  S3-compatible / managed prod), selected by env (`.env.example`). Postgres is fixed (16).
- **Coordinates & organism are persisted explicitly** wherever a positioned entity is stored
  (`coordinate_systems.md`).

## Stack (from `architecture_overview.md` §6)

Postgres 16 (SQLAlchemy 2 + psycopg3, Alembic migrations) · Redis 7 (queue, cache, ephemeral
checkpoint state) · pluggable object store (`OBJECT_STORE_URL`) · pluggable vector index. Code lives
in `src/backend/cellxp/storage/`. Diagram: `documentation/diagrams/database_schema.mmd`.
