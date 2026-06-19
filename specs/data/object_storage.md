# Object Storage

> Status: Draft v0.1. Defines where **large/opaque payloads** live (artifact data, model outputs,
> uploads) and how they're keyed, addressed, served, and retained. Backend is **pluggable**
> (`OBJECT_STORE_URL`: `file://` dev → S3-compatible prod). Postgres holds only metadata + the object
> **key** (`relational_schema.md`). Implementation: `storage/object_store.py`. Content-addressing +
> integrity rules come from `provenance_model.md` §6.

## 1. Purpose & scope

Defines the object-store contract: the put/get/delete interface, what belongs here vs Postgres, the
key scheme, content addressing, MIME handling, access/serving, and retention. Does **not** define the
relational metadata rows (`relational_schema.md`) or RAG embeddings (`vector_index.md`).

## 2. Interface (backend-agnostic)

```python
class ObjectStore(Protocol):
    def put(self, data: bytes, *, content_type: str, key: str | None = None) -> ObjectRef: ...
    def get(self, key: str) -> bytes: ...
    def open(self, key: str) -> BinaryIO: ...        # streaming for large blobs
    def exists(self, key: str) -> bool: ...
    def url(self, key: str, *, expires_s: int | None = None) -> str: ...  # signed/served URL
    def delete(self, key: str) -> None: ...          # session-deletion path only

class ObjectRef(BaseModel):
    key: str
    content_type: str
    size: int
    hash: str            # sha256, hex
```

Backends implement this Protocol: `file://` (local FS, dev/local-first), S3-compatible (prod). The
agent/services depend only on the Protocol (`NFR-11`, pluggability).

## 3. What goes here vs Postgres

| Store here (object) | Keep in Postgres |
|---|---|
| 3D structures (PDB/mmCIF), contact-map arrays, large track arrays | artifact metadata, titles, summaries |
| Plot data / rendered figures, image exports | evidence `value` (small structured JSON) |
| Origami design files (cadnano/JSON), guide tables (large) | guide-table summary / top-N preview |
| User uploads (FASTA/VCF/BCF, files) | normalized inputs, identifiers, coordinates |
| Any payload `> OBJECT_INLINE_MAX` (default 16 KiB) or binary | anything queried/filtered relationally |

**Rule:** if it's large, binary, or only ever fetched whole by `id`, it's an object. If it's queried,
filtered, or small structured data, it's a JSONB column. Threshold `OBJECT_INLINE_MAX` is configurable.

## 4. Keys & content addressing

- Default key is **content-addressed**: `cas/<sha256>` so identical payloads dedupe and integrity is
  verifiable (`provenance_model.md` §6).
- A human-navigable alias namespace is also written for run-scoped browsing:
  `runs/<run_id>/<artifact_type>/<artifact_id>.<ext>` → pointer to the CAS object (or a copy for
  `file://`).
- Uploads: `uploads/<session_id>/<upload_id>__<original_name>` (original name preserved for UX; content
  hashed for integrity).
- Keys are opaque to clients; access is always via the API/`url()`, never by guessing paths.

## 5. Serving & access control

- Clients never get raw bucket access. The API issues **short-lived signed URLs** (`url(expires_s=…)`)
  or streams through an artifact endpoint (`api_contracts.md`, `FR-29`).
- Authorization is checked at the API against the owning `run`/`session`/`user` before a URL is issued.
- `content_type` is stored and returned so the frontend renders correctly (e.g. `chemical/x-pdb`,
  `image/png`, `application/json`).

## 6. Integrity, immutability & retention

- Objects are **immutable**: a new result is a new key (no overwrite). Content hash recorded in the
  referencing `step`/`artifact` row; mismatch on read → integrity error (`PROV-4`).
- **Retention tiers:**
  - *Pinned-by-run* — referenced by a persisted artifact/evidence; retained for the run/session life.
  - *Cache* — deterministic step outputs reusable across runs; eligible for TTL eviction
    (`OBJECT_CACHE_TTL`), re-derivable from provenance if evicted.
- **Deletion** happens only via the session/run deletion path (`provenance_model.md` §8) and is
  audited (`audit_log.md`). Local-first deployments keep all objects on user infrastructure (`NFR-7`).

## 7. Config

`OBJECT_STORE_URL` (e.g. `file:///var/lib/cellxp/artifacts`, `s3://bucket`,
`https://minio:9000/bucket`), plus backend creds via env (never hard-coded, `config/settings.py`).
`OBJECT_INLINE_MAX`, `OBJECT_CACHE_TTL` tunables.

## 8. Requirements (testable)

- **OS-1** Payloads above `OBJECT_INLINE_MAX` or of binary type are stored as objects; Postgres holds
  only the key + metadata (`RS-5`).
- **OS-2** Default keys are content-addressed; identical bytes produce the same key (dedupe).
- **OS-3** Stored `hash` verifies on read; mismatch raises an integrity error.
- **OS-4** Objects are immutable (no overwrite of an existing key with different content).
- **OS-5** Client access is only via signed/served URLs authorized against the owning run/session.
- **OS-6** The same code path works against `file://` and S3-compatible backends (interface test with
  both).

## 9. Open questions

- Cross-run CAS dedupe scope (global vs per-session) under local-first isolation.
- Whether to encrypt-at-rest by default for sensitive sessions (e.g. personal genomes, FC-1).
- Multipart/streaming upload limits for very large user files (whole genomes).

## 10. Related specs

`provenance_model.md` (§6) · `relational_schema.md` · `vector_index.md` ·
`specs/interface/artifact_model.md` · `specs/interface/api_contracts.md` ·
`documentation/explanation/architecture_overview.md` §6.
