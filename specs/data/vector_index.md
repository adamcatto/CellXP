# Vector Index

> Status: Draft v0.1. Defines the **embedding + chunk store** that powers retrieval-augmented
> generation (the `rag` capability, `FR-20`). Backend is **pluggable** (interface-first: local
> pgvector/Chroma dev → managed vector DB prod). Implementation: `storage/vector_store.py`; consumers:
> `services/rag/*`, `specs/agent/capability-subgraphs/rag.md`. Every retrieved chunk must carry the
> citation provenance defined in `provenance_model.md`.
>
> **Implementation checkpoint (2026-06-21):** `storage/rag_vector_index.py` implements the protocol
> as a persistent local SQLite cosine index. It is intended for development and small corpora;
> production-scale managed and pgvector adapters remain pluggable deployment work.

## 1. Purpose & scope

Defines what is embedded and indexed, the chunk record schema, namespaces/collections, the query
contract, and how retrieved chunks become cited evidence. Does **not** define retrieval *strategy*
(reranking, query expansion — `services/rag/retriever.py` + `rag.md`) or how claims are extracted
(`services/rag/extract_claims.py`).

## 2. Interface (backend-agnostic)

```python
class RagVectorIndex(Protocol):
    def upsert(self, chunks: list[Chunk]) -> None: ...
    def query(self, embedding: list[float], *, k: int,
              embedding_model: str, namespace: str,
              filters: dict | None = None) -> list[ScoredChunk]: ...
    def delete(self, ids: list[str] | None = None, *, namespace: str,
               filters: dict | None = None) -> int: ...

class Chunk(BaseModel):
    id: str
    namespace: str                  # collection (see §4)
    text: str                       # the chunk content (also persisted/object-stored if large)
    embedding: list[float]          # model-specific dimensionality
    metadata: ChunkMetadata

class ScoredChunk(BaseModel):
    chunk: Chunk
    score: float                    # similarity (cosine by default)

class ChunkMetadata(BaseModel):
    source_kind: Literal["literature", "database", "internal"]
    citation: str                   # DOI / PMID / accession / URL (REQUIRED)
    title: str | None = None
    source_id: str | None = None    # document id
    section: str | None = None
    organism: str | None = None     # for filterable applicability
    published: str | None = None    # date
    embedding_model: str            # provenance: model + version used to embed
    ingested_at: str
```

Consumers depend only on the Protocol (pluggability, `NFR-11`).

The local implementation names these models `RagVectorChunk`, `RagScoredChunk`, and
`RagChunkMetadata` to avoid collision with generic domain names. `embedding_model` is the comparison
key and includes model and version (`model@version`). A namespace rejects inserts or queries with a
different model key or vector dimensionality until it is rebuilt.

## 3. What gets indexed

- **Literature** — abstracts/passages from PubMed/biorxiv and provided papers (`services/rag/pubmed.py`).
- **Curated database docs** — annotation notes, guideline text, model/assay caveats (incl. the
  community notes, `documentation/community-notes/`).
- **Internal** — selected spec/reference text to ground the agent about its own capabilities (optional).

Each source MUST resolve to a **citation** before indexing; un-citable text is not indexed (no
ungrounded RAG, `evidence_and_confidence.md` §8).

## 4. Namespaces / collections

One index, partitioned by `namespace` so retrieval is scoped and filterable: e.g. `literature`,
`db_docs`, `community_notes`, `internal_docs`. Queries target a namespace + metadata `filter`
(e.g. `organism`, `published >=`). Namespacing also supports per-session/private corpora under
local-first isolation.

## 5. Embedding model

- Configured via env (`EMBEDDING_MODEL`, `EMBEDDING_DIM`); a local-first default consistent with the
  Ollama-first stance (`llm_service.md`), pluggable to remote embedders.
- The embedding model **id+version is provenance** (`metadata.embedding_model`): chunks embedded with
  different models are not comparable. Changing the model requires a **re-embed migration** of the
  affected namespace(s); mixed-model results within one query are disallowed.
- Distance metric: cosine (default); fixed per namespace.
- The SQLite backend scores vectors in process. This provides deterministic persistence without an
  optional native dependency, but is not intended for large production corpora.

## 6. Retrieval → evidence flow

1. Query embedded with the same model as the target namespace → `query(k, namespace, filter)`.
2. `ScoredChunk`s are reranked/filtered by the rag service (`rag.md`).
3. Each chunk used to support a claim becomes an `EvidenceItem` with `source_kind="literature"`
   (or `database`), `provenance.citations = [chunk.metadata.citation]`, and the similarity score noted
   in `provenance.params`. The report's inline citation maps back to it (`state_schema.md` §11).

So a vector hit is never an answer by itself — it's traced to a citation and folded through the normal
evidence pipeline (`evidence_integration.md`).

## 7. Lifecycle & retention

- Ingestion is idempotent on `chunk.id` (content-hash of `source_id + section + text`), so re-ingesting
  a source dedupes.
- Corpus rebuilds (new embedding model, re-chunking) are migrations, versioned like Alembic
  (`relational_schema.md` §7) but for the index.
- Private/session corpora are deletable via the session-deletion path and audited
  (`provenance_model.md` §8).
- `LocalRagBackend` requires private documents to use a `private/` or `session/` namespace. Wiring
  session deletion to audit persistence remains owned by the storage/session integration layer.

## 8. Requirements (testable)

- **VI-1** Every indexed chunk has a non-empty `citation` and an `embedding_model` tag.
- **VI-2** A query only returns chunks embedded with the query's embedding model (no cross-model
  mixing); namespace + filter are honored.
- **VI-3** Each retrieved chunk that informs the answer yields an `EvidenceItem` with its citation
  (round-trip from report citation → chunk).
- **VI-4** Ingestion is idempotent on `chunk.id` (re-ingest does not duplicate).
- **VI-5** The same retrieval code path works against the local and managed backends (interface test).
- **VI-6** Changing `EMBEDDING_MODEL` without re-embedding a namespace is rejected (guard).

## 9. Open questions

- Default local embedding model + dimensionality (quality vs local footprint).
- Hybrid (BM25 + vector) search ownership: index vs retriever service.
- Per-session private corpora isolation mechanism (separate namespaces vs separate indexes).
- Production-scale backend selection and its shared protocol-conformance fixture.

## 10. Related specs

`specs/agent/capability-subgraphs/rag.md` · `services/rag/*` · `provenance_model.md` ·
`evidence_and_confidence.md` · `evidence_integration.md` · `object_storage.md` ·
`llm_service.md` · `documentation/community-notes/`.

## 11. Verification

The deterministic T1 index contract covers provenance, idempotent upsert, cosine ranking,
namespace/filter isolation, persistence, deletion, model migration guards, and dimension guards:

```bash
python -m pytest tests/unit/test_rag_sqlite_vector_index.py -q
```

The ingestion-to-context citation round trip is covered by:

```bash
python -m pytest tests/unit/test_rag_local_backend.py -q
```
