"""RAG service package (X2); importing it registers :class:`RagService`."""

from .schemas import (
    CitationExtractRequest,
    CitationRecord,
    CitationSet,
    ContextBundle,
    ContextRequest,
    ContextSnippet,
    IndexDocument,
    IndexRequest,
    IndexResult,
    RagBackend,
    RetrieveRequest,
    RetrievedChunk,
    RetrievedDocument,
    SearchHit,
    SearchRequest,
    SearchResult,
)
from .service import RagService

__all__ = [
    "RagService",
    "RagBackend",
    "SearchRequest",
    "SearchResult",
    "SearchHit",
    "RetrieveRequest",
    "RetrievedDocument",
    "RetrievedChunk",
    "CitationExtractRequest",
    "CitationRecord",
    "CitationSet",
    "IndexDocument",
    "IndexRequest",
    "IndexResult",
    "ContextRequest",
    "ContextSnippet",
    "ContextBundle",
]
