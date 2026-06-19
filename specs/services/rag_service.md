# RAG Service

> Status: Draft v0.1. Logical service contract for literature/database retrieval, citation
> extraction, chunking, embedding, and evidence grounding. Impl:
> `src/backend/cellxp/services/rag/`. Data contracts:
> `specs/data/vector_index.md`, `specs/data/provenance_model.md`. Catalog:
> `documentation/reference/external_models_and_services.md` §17.

## 1. Purpose

Retrieve and normalize scientific evidence from literature and databases so generated reports can
cite primary sources and database records. This service supplies evidence; it does not synthesize the
final answer.

## 2. Operations

```python
class RagService(Service):
    def search(self, request: SearchRequest) -> ServiceResult[SearchResult]: ...
    def retrieve(self, request: RetrieveRequest) -> ServiceResult[RetrievedDocument]: ...
    def extract_citations(self, request: CitationExtractRequest) -> ServiceResult[CitationSet]: ...
    def index_documents(self, request: IndexRequest) -> ServiceResult[IndexResult]: ...
    def answer_context(self, request: ContextRequest) -> ServiceResult[ContextBundle]: ...
```

`answer_context` returns ranked evidence snippets and metadata for the report generator and evidence
integration nodes.

## 3. Sources

Supported sources include PubMed/PMC, bioRxiv/medRxiv, Ensembl/UCSC/NCBI, UniProt, Reactome, KEGG,
GO, ChEMBL/ChEBI where configured, and local user-provided documents. Each source adapter declares
release/date, access method, citation format, and terms/limits.

## 4. Inputs

Requests may be natural-language search queries, structured biological entities, accessions, DOIs,
PMIDs, or local document refs. Entity-aware retrieval SHOULD include organism, gene/protein IDs,
variant IDs, assay terms, and synonym expansions from the reference service.

## 5. Outputs & Artifacts

RAG outputs are primarily `EvidenceItem`s and citation metadata, not visual artifacts.

| Output | Artifact type | Storage |
|---|---|---|
| citation set | `citation_table` | inline metadata |
| retrieved chunks | none by default | vector index + Postgres metadata |
| full retrieved docs | `document_ref` where user-visible | object storage if cached |
| evidence bundle | none | inline ranked evidence IDs |

## 6. Provenance & Confidence

Every retrieved claim records source, accession/PMID/DOI/URL, publication/version date, retrieval
query, rank score, chunk ID, and timestamp. Confidence reflects source type, retrieval rank,
recency/curation status, directness to the claim, and agreement with other evidence.

## 7. Vector Index Contract

Chunks persisted for reuse MUST follow `specs/data/vector_index.md`: namespace, embedding model,
chunk hash, source metadata, and provenance link. The service MAY delegate embeddings to the LLM
service or a dedicated embedding provider, but the embedding model/version is always recorded.

## 8. Failure Modes

- no hits: valid empty context with query metadata;
- source unavailable/rate-limited: recoverable `RunError`, use cached entries where allowed;
- ambiguous accession: return candidates;
- paywalled/full text unavailable: cite accessible metadata/abstract and mark limitation;
- stale local index: warn with indexed-at timestamp.

## 9. Requirements

- **RAG-1** Every citation in a report MUST resolve to a persisted evidence item or citation record.
- **RAG-2** Retrieval chunks MUST record source IDs, source release/date, embedding model, and chunk
  hash.
- **RAG-3** Search failure MUST not fabricate citations.
- **RAG-4** User-uploaded/private documents MUST remain in the deployment's configured storage and
  namespace.
- **RAG-5** Retrieved context MUST preserve enough metadata for the report generator to build a
  citation map.

## 10. Related

`specs/data/vector_index.md` · `specs/agent/evidence_integration.md` ·
`documentation/explanation/evidence_and_confidence.md` · `specs/interface/artifact_model.md`.
