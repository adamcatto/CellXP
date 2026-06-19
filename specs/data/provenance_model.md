# Provenance Model

> Status: Draft v0.1 — **keystone of the data layer.** Defines what CellXP records so that
> any claim, evidence item, or artifact can be **reproduced and audited** (`FR-24`). Binding in-state
> shapes are `state_schema.md` §8–§10 (`Step`, `EvidenceItem`, `Provenance`, `ArtifactRef`); semantics
> are `documentation/explanation/evidence_and_confidence.md`; persistence is `relational_schema.md` +
> `object_storage.md`; consequential-event trail is `audit_log.md`.

## 1. Purpose & scope

This spec defines the **provenance graph** — the set of linked records that answer, for any output:
*what produced it, from what inputs, with which tool/model at which version, with what parameters,
when, and on whose authority.* It governs identity, versioning, content addressing, immutability, and
reproducibility. It does **not** define DDL (`relational_schema.md`) or confidence math
(`evidence_and_confidence.md`).

## 2. Principles

- **Reproducible by construction.** Given a persisted run, re-executing its steps with the recorded
  tool versions + params + inputs MUST yield equivalent results (modulo documented nondeterminism, §7).
- **Attributable.** Every substantive claim links to ≥1 `EvidenceItem`; every evidence item links to
  the `Step` that produced it and the `Subtask`/`Run` it belongs to. No orphan claims (`FR-23/24`).
- **Append-only.** Provenance is insert-only; corrections add records, never mutate/delete history.
- **Versioned everything.** Tools, models, datasets, reference assemblies, prompts, and the schema
  itself carry versions (§4). "AlphaGenome" is not provenance; "AlphaGenome `<rev>`" is.
- **Content-addressable payloads.** Large/opaque outputs are referenced by a content hash so identical
  results dedupe and tampering is detectable (§6, `object_storage.md`).

## 3. The provenance graph

Nodes (each a persisted, ID'd entity; see `relational_schema.md`):

```
Session ─< Run ─< Subtask ─< Step ─< EvidenceItem
                    │           └──< (object payloads, content-addressed)
                    └──< ArtifactRef ─ (evidence_ids) ─> EvidenceItem
Run ─< Message      Run ─< ReviewItem ─> ArtifactRef     Run ─< RunError
```

Edges are foreign keys / ID arrays carried in state and persisted. Traversal from a report sentence →
`citation_map` → `EvidenceItem` → `Step` → tool/version/params/inputs → object payload is the
**reproduction path** and the **audit path**.

## 4. What every `Step` and `EvidenceItem` records (`Provenance`)

Per `state_schema.md` §9, each carries:

| Field | Meaning | Notes |
|---|---|---|
| `tool` | service/model/db identity | catalog key (`external_models_and_services.md`) |
| `tool_version` | exact version/revision | model weights rev, db release, package version, prompt hash |
| `params` | call parameters | e.g. tissue/assay, thresholds, seeds |
| `inputs` | **normalized** inputs used | organism+assembly+coords explicit (`coordinate_systems.md`) |
| `output_ref` | pointer to result | object-store key or evidence id |
| `citations` | DOI / PMID / accession / URL | for `database`/`literature` evidence |
| `timestamp` | UTC ISO-8601 | when produced |
| `input_hash` / `output_hash` | content hashes | reproducibility + dedupe (§6) |

**Version capture** is mandatory for `model` and `database` evidence; a step whose `tool_version` is
unknown MUST record `"unknown"` explicitly and lower confidence accordingly (it is not silently
omitted).

## 5. Identity & addressing

- IDs are **stable, opaque, globally unique** (UUIDv7 or ULID — time-orderable; see
  `relational_schema.md` §3). Generated at creation, never reused.
- `run_id` is the universal join key; `session_id` groups runs in a workspace (`session_types.md`).
- Every ID is client-visible so the UI can deep-link (`FR-29/30`, `state_schema.md` §2).

## 6. Content addressing & integrity

- Large/opaque payloads (structures, track arrays, plot data, uploads) are stored in the object store
  under a key derived from their **content hash** (e.g. `sha256`), so identical outputs dedupe and any
  later read can verify integrity (`object_storage.md` §4).
- `input_hash` over normalized inputs+params lets the system **cache** deterministic step results
  (`tool_use_policy.md` §10) and prove two evidence items derived from identical inputs.
- Hashes are recorded in the `Step`/`EvidenceItem` provenance; a mismatch on read is a data-integrity
  error (`domain/errors.py`).

## 7. Reproducibility & nondeterminism

- **Deterministic** steps (lookups, coordinate math, deterministic models) MUST reproduce exactly;
  the cache key is `(tool, tool_version, params, input_hash)`.
- **Nondeterministic** steps (sampling-based generation, stochastic design, LLM calls) record the
  **seed** where supported and are flagged `nondeterministic=true`; reproduction means *distributional*
  equivalence, and the report must not over-claim exactness. Seedless nondeterminism is documented in
  the step's provenance.
- The reasoning-LLM prompt + model + decoding params are themselves provenance for any
  LLM-synthesized text (prompt hash in `tool_version`/`params`).

## 8. Retention, corrections & privacy

- Provenance and audit records are **retained for the life of the run/session** and are insert-only.
- Corrections/retractions are new records that reference the superseded one (`supersedes` id); nothing
  is hard-deleted within a run's lifetime.
- **Deletion** (user/session deletion, GDPR-style erasure) is a session-level operation that removes
  the run subtree and its object payloads; it is itself an audited event (`audit_log.md`). Local-first
  deployments keep all of this on the user's infrastructure (`NFR-7`).
- Sensitive inputs (e.g. personal genomes, FC-1) follow the same model with stricter access; flagged
  at the session level.

## 9. Requirements (testable)

- **PROV-1** Every persisted `EvidenceItem` has a non-empty `Provenance` with `tool`, `tool_version`
  (may be `"unknown"`), `inputs`, and `timestamp`. Coverage ≥95% across substantive claims
  (`success_metrics.md` D2).
- **PROV-2** Every `ArtifactRef` links to the `Subtask`/`Step` that produced it and to its supporting
  `evidence_ids`.
- **PROV-3** No provenance row is updated or deleted in place during a run's lifetime; corrections are
  new rows with `supersedes`.
- **PROV-4** Object payloads are content-addressed; stored hash matches on read or an integrity error
  is raised.
- **PROV-5** Deterministic steps with equal `(tool, tool_version, params, input_hash)` return cached
  results and are marked as cache hits in provenance.
- **PROV-6** Given a completed run, a `reproduce(run_id)` routine can re-derive each deterministic
  evidence item from recorded inputs/versions (regression test, `specs/evaluation/regression_tests.md`).
- **PROV-7** Review decisions, refusals, and side effects are mirrored to `audit_log.md` with actor +
  timestamp.

## 10. Open questions

- Canonical hash algorithm + normalization rules for `input_hash` (JSON canonicalization).
- How long to retain object payloads for cache vs run history (TTL vs pinned-by-run).
- Cross-run dedupe of identical model calls (global content store vs per-run).

## 11. Related specs

`state_schema.md` §8–§10 · `evidence_and_confidence.md` · `relational_schema.md` ·
`object_storage.md` · `audit_log.md` · `tool_use_policy.md` · `coordinate_systems.md` ·
`success_metrics.md` (D2) · `specs/evaluation/regression_tests.md`.
