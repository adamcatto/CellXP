# Audit Log

> Status: Draft v0.1. Defines the **append-only record of consequential events** — review decisions,
> safety refusals, actionable outputs, side effects, and access/lifecycle events. Complements the
> per-run provenance graph (`provenance_model.md`): provenance answers *how a result was produced*; the
> audit log answers *who did/decided/was-refused what, when*. Persisted in Postgres
> (`relational_schema.md`); written by the review gate, safety model, and side-effect paths.

## 1. Purpose & scope

A single, immutable, queryable trail of events that have **safety, accountability, or compliance**
weight — distinct from the full step/evidence trace (which lives in provenance). Required by the
human-review policy (`human_review_policy.md` §5), the safety model (`safety_model.md`), and the
reproducible-trace principle (`FR-24`). Does **not** duplicate every step (that's `steps`); it records
*consequential* events only.

## 2. What is audited (event catalog)

| `event_type` | When | Key payload |
|---|---|---|
| `review.requested` | actionable output gated | review_item id, subject_ref, reason, risks |
| `review.decided` | reviewer approves/rejects/requests-changes | decision, decided_by, note, evidence_ids |
| `safety.refused` | `risk=block` refusal | reason, category, query digest (not raw if sensitive) |
| `safety.restricted` | `risk=restrict` forces gate | category, subtask ref |
| `actionable.emitted` | a recommendation released post-approval | artifact id, type, approving review_item |
| `side_effect.performed` | file written/committed / external mutation | target, summary, authorizing actor |
| `session.created` / `session.deleted` | workspace lifecycle | session id, type |
| `data.deleted` | run/session/object erasure | scope, requested_by, counts |
| `access.url_issued` | signed URL minted for an object | object key, run/session, expires |
| `config.changed` | provider/model/policy change affecting behavior | what changed (no secrets) |

The set is extensible; new event types are added by migration with a documented payload shape.

## 3. Record schema

```python
class AuditEntry(BaseModel):
    id: str                       # ULID/UUIDv7
    event_type: str               # from the catalog (§2)
    actor: Actor                  # who/what caused it
    run_id: str | None = None
    session_id: str | None = None
    subject_ref: str | None = None   # artifact/subtask/object/session under action
    payload: dict[str, Any] = {}     # event-specific, secret-free, sensitive-data-minimized
    at: str                          # UTC ISO-8601
    prev_hash: str | None = None     # hash of previous entry (tamper-evidence, §5)
    hash: str                        # hash(this entry incl. prev_hash)

class Actor(BaseModel):
    kind: Literal["user", "agent", "system"]
    id: str | None = None         # user id when kind == user
```

Table `audit_log` is **append-only** (`relational_schema.md` §4): no `UPDATE`/`DELETE` in normal
operation. Index: `(run_id, at)`, `(session_id, at)`, `(event_type, at)`.

## 4. Privacy & minimization

- Payloads are **secret-free** (never tokens/keys/credentials) and **sensitive-data-minimized**: store
  references/digests, not raw sensitive inputs (e.g. for personal-genome sessions, FC-1, log the action
  and ids, not the variants).
- Local-first deployments keep the audit log on the user's infrastructure (`NFR-7`).
- A `data.deleted` event records erasures; the audit log itself is retained (it is the record *that*
  deletion happened), holding only non-sensitive references.

## 5. Integrity (tamper-evidence)

- Entries form a **hash chain**: each `hash = H(payload-fields ‖ prev_hash)`, so any retroactive edit
  breaks the chain and is detectable. (Lightweight integrity, not full cryptographic non-repudiation.)
- Verification routine walks the chain per `(run_id|session_id)` partition; a break is a security
  finding (`safety_model.md`).

## 6. Relationship to provenance & review state

- **Provenance** (`provenance_model.md`) = complete production trace, per result. **Audit log** =
  consequential events, cross-run, accountability-focused. They cross-reference by `run_id` and ids.
- `review_items` (relational) hold current decision state; the audit log holds the **immutable
  decision events** (`review.decided`). The table is the "now"; the log is the "history".

## 7. Requirements (testable)

- **AL-1** Every gate decision (`review.decided`), safety refusal (`safety.refused`), released
  actionable output (`actionable.emitted`), and side effect (`side_effect.performed`) writes an audit
  entry with actor + timestamp (ties to `PROV-7`, `human_review_policy.md` §5).
- **AL-2** The table rejects in-place updates/deletes; entries are insert-only.
- **AL-3** Audit payloads contain no secrets and no raw sensitive inputs (lint/test on writers).
- **AL-4** The hash chain verifies; a mutated entry is detected by the verification routine.
- **AL-5** Erasures (`data.deleted`) are themselves audited and do not remove prior audit entries.
- **AL-6** No recommended actionable output exists without a preceding `review.decided(approved)` for
  its subject (joins audit ↔ artifacts; mirrors `human_review_policy.md` §8, metric D5).

## 8. Open questions

- Retention horizon for audit entries vs run/session deletion (regulatory vs storage).
- Whether to support exportable signed audit bundles for compliance.
- Reviewer identity/roles in multi-user deployments (`human_review_policy.md` §10).

## 9. Related specs

`provenance_model.md` · `relational_schema.md` · `human_review_policy.md` ·
`documentation/explanation/safety_model.md` · `state_schema.md` §12 · `success_metrics.md` (D5) ·
`object_storage.md` (`access.url_issued`).
