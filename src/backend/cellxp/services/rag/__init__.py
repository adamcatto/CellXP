"""RAG service package (X2); importing it registers :class:`RagService`."""

from .pubmed import NcbiLiteratureClient
from .retriever import LocalRagBackend, TextEmbedder
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
    RetrievedChunk,
    RetrievedDocument,
    RetrieveRequest,
    SearchHit,
    SearchRequest,
    SearchResult,
)
from .service import RagService

__all__ = [
    "CitationExtractRequest",
    "CitationRecord",
    "CitationSet",
    "ContextBundle",
    "ContextRequest",
    "ContextSnippet",
    "IndexDocument",
    "IndexRequest",
    "IndexResult",
    "LocalRagBackend",
    "NcbiLiteratureClient",
    "RagBackend",
    "RagService",
    "RetrieveRequest",
    "RetrievedChunk",
    "RetrievedDocument",
    "SearchHit",
    "SearchRequest",
    "SearchResult",
    "TextEmbedder",
]
