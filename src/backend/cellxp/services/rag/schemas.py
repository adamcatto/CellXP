"""RAG service request/result schemas and injectable backend contract (X2, FR-20)."""

from __future__ import annotations

from typing import Literal, Protocol, runtime_checkable

from pydantic import BaseModel, Field, field_validator


SourceType = Literal["literature", "database"]


class RetrievalContext(BaseModel):
    """Optional biological framing shared by retrieval operations."""

    organism: str | None = None
    assembly: str | None = None


class SearchRequest(RetrievalContext):
    query: str
    sources: list[str] | None = None
    limit: int = Field(default=10, ge=1, le=100)
    published_after: str | None = None

    @field_validator("query")
    @classmethod
    def _query_non_empty(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("query must be non-empty")
        return value.strip()


class SearchHit(BaseModel):
    source: str
    source_type: SourceType
    source_id: str
    title: str
    citation: str
    url: str | None = None
    publication_date: str | None = None
    source_release: str | None = None
    rank_score: float = Field(ge=0.0, le=1.0)
    snippet: str | None = None


class SearchResult(BaseModel):
    query: str
    hits: list[SearchHit] = Field(default_factory=list)


class RetrieveRequest(RetrievalContext):
    source: str
    identifier: str


class RetrievedChunk(BaseModel):
    chunk_id: str
    text: str
    chunk_hash: str
    source_id: str
    source_release: str
    embedding_model: str
    embedding_version: str = "unknown"


class RetrievedDocument(BaseModel):
    source: str
    source_type: SourceType
    source_id: str
    title: str
    citation: str
    url: str | None = None
    publication_date: str | None = None
    storage_ref: str | None = None
    chunks: list[RetrievedChunk] = Field(default_factory=list)


class CitationExtractRequest(RetrievalContext):
    text: str
    document_refs: list[str] = Field(default_factory=list)


class CitationRecord(BaseModel):
    marker: str
    source: str
    source_type: SourceType
    source_id: str
    citation: str
    claim: str
    url: str | None = None
    publication_date: str | None = None
    confidence_score: float = Field(ge=0.0, le=1.0)
    evidence_id: str | None = None


class CitationSet(BaseModel):
    citations: list[CitationRecord] = Field(default_factory=list)
    citation_map: dict[str, str] = Field(default_factory=dict)


class IndexDocument(BaseModel):
    source: str
    source_type: SourceType
    source_id: str
    source_release: str
    text_ref: str
    namespace: str
    private: bool = False


class IndexRequest(RetrievalContext):
    documents: list[IndexDocument] = Field(default_factory=list)
    embedding_model: str
    embedding_version: str = "unknown"


class IndexResult(BaseModel):
    indexed_documents: int = 0
    indexed_chunks: int = 0
    namespace: str | None = None


class ContextRequest(SearchRequest):
    max_snippets: int = Field(default=8, ge=1, le=50)


class ContextSnippet(BaseModel):
    text: str
    chunk_id: str
    chunk_hash: str
    source: str
    source_type: SourceType
    source_id: str
    source_release: str
    citation: str
    embedding_model: str
    embedding_version: str = "unknown"
    rank_score: float = Field(ge=0.0, le=1.0)
    evidence_id: str | None = None


class ContextBundle(BaseModel):
    query: str
    snippets: list[ContextSnippet] = Field(default_factory=list)
    citation_map: dict[str, str] = Field(default_factory=dict)


@runtime_checkable
class RagBackend(Protocol):
    """Transport-neutral retrieval, citation, and vector-index implementation."""

    def search(self, request: SearchRequest) -> SearchResult: ...

    def retrieve(self, request: RetrieveRequest) -> RetrievedDocument | None: ...

    def extract_citations(self, request: CitationExtractRequest) -> CitationSet: ...

    def index_documents(self, request: IndexRequest) -> IndexResult: ...

    def answer_context(self, request: ContextRequest) -> ContextBundle: ...
