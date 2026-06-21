"""Concrete local RAG backend composed from literature, embedding, and vector adapters."""

from __future__ import annotations

import hashlib
import re
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Protocol, runtime_checkable

from cellxp.domain.clock import utc_now_iso
from cellxp.storage.rag_vector_index import (
    RagChunkMetadata,
    RagVectorChunk,
    RagVectorIndex,
)

from .pubmed import NcbiLiteratureClient
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
    RetrieveRequest,
    RetrievedDocument,
    SearchRequest,
    SearchResult,
)


@runtime_checkable
class TextEmbedder(Protocol):
    model: str
    version: str

    def embed(self, texts: Sequence[str]) -> list[list[float]]: ...


class LocalRagBackend:
    """RAG backend for NCBI retrieval and a local or injected vector index."""

    def __init__(
        self,
        *,
        literature: NcbiLiteratureClient,
        vector_index: RagVectorIndex,
        embedder: TextEmbedder,
        default_namespace: str = "literature",
        text_loader: Callable[[str], str] | None = None,
        chunk_characters: int = 2_000,
    ) -> None:
        if chunk_characters < 100:
            raise ValueError("chunk_characters must be at least 100")
        self._literature = literature
        self._vectors = vector_index
        self._embedder = embedder
        self._default_namespace = default_namespace
        self._text_loader = text_loader or _read_local_text
        self._chunk_characters = chunk_characters

    def search(self, request: SearchRequest) -> SearchResult:
        sources = {source.casefold() for source in request.sources or ["pubmed"]}
        if not sources.intersection({"pubmed", "pmc", "pubmed central"}):
            return SearchResult(query=request.query)
        return self._literature.search_pubmed(request)

    def retrieve(self, request: RetrieveRequest) -> RetrievedDocument | None:
        return self._literature.retrieve(request.source, request.identifier)

    def extract_citations(self, request: CitationExtractRequest) -> CitationSet:
        markers = list(dict.fromkeys(re.findall(r"\[\d+\]", request.text)))
        citations: list[CitationRecord] = []
        for marker, reference in zip(markers, request.document_refs, strict=False):
            source, source_id, url = _reference_metadata(reference)
            citations.append(
                CitationRecord(
                    marker=marker,
                    source=source,
                    source_type="literature",
                    source_id=source_id,
                    citation=reference,
                    claim=_claim_for_marker(request.text, marker),
                    url=url,
                    confidence_score=1.0,
                )
            )
        return CitationSet(citations=citations)

    def index_documents(self, request: IndexRequest) -> IndexResult:
        if not request.documents:
            return IndexResult()
        namespaces = {document.namespace for document in request.documents}
        if len(namespaces) != 1:
            raise ValueError("one index request must target exactly one namespace")
        if request.embedding_model != self._embedder.model:
            raise ValueError(
                f"configured embedder is {self._embedder.model!r}, "
                f"not {request.embedding_model!r}"
            )
        if request.embedding_version not in {"unknown", self._embedder.version}:
            raise ValueError(
                f"configured embedding version is {self._embedder.version!r}, "
                f"not {request.embedding_version!r}"
            )
        model_key = _embedding_key(self._embedder.model, self._embedder.version)
        chunks: list[tuple[IndexDocument, str, str]] = []
        for document in request.documents:
            if document.private and not document.namespace.startswith(("private/", "session/")):
                raise ValueError("private documents require a private/ or session/ namespace")
            text = self._text_loader(document.text_ref)
            for passage in _split_text(text, self._chunk_characters):
                chunks.append((document, passage, _sha256(passage)))
        embeddings = self._embedder.embed([passage for _, passage, _ in chunks])
        if len(embeddings) != len(chunks):
            raise ValueError("embedder returned a different number of vectors than input texts")
        ingested_at = utc_now_iso()
        vector_chunks = [
            RagVectorChunk(
                id=_sha256(f"{document.source_id}:{chunk_hash}"),
                namespace=document.namespace,
                text=passage,
                embedding=embedding,
                metadata=RagChunkMetadata(
                    source_kind=document.source_type,
                    citation=document.source_id,
                    source_id=document.source_id,
                    source_release=document.source_release,
                    embedding_model=model_key,
                    ingested_at=ingested_at,
                    organism=request.organism,
                ),
            )
            for (document, passage, chunk_hash), embedding in zip(
                chunks, embeddings, strict=True
            )
        ]
        self._vectors.upsert(vector_chunks)
        return IndexResult(
            indexed_documents=len(request.documents),
            indexed_chunks=len(vector_chunks),
            namespace=next(iter(namespaces)),
        )

    def answer_context(self, request: ContextRequest) -> ContextBundle:
        model_key = _embedding_key(self._embedder.model, self._embedder.version)
        query_vectors = self._embedder.embed([request.query])
        if len(query_vectors) != 1:
            raise ValueError("embedder must return exactly one query vector")
        filters = {"organism": request.organism} if request.organism else None
        scored = self._vectors.query(
            query_vectors[0],
            embedding_model=model_key,
            k=request.max_snippets,
            namespace=self._default_namespace,
            filters=filters,
        )
        snippets = [
            ContextSnippet(
                text=item.chunk.text,
                chunk_id=item.chunk.id,
                chunk_hash=f"sha256:{_sha256(item.chunk.text)}",
                source=_source_label(item.chunk.metadata.source_id),
                source_type=(
                    "literature"
                    if item.chunk.metadata.source_kind == "literature"
                    else "database"
                ),
                source_id=item.chunk.metadata.source_id or item.chunk.id,
                source_release=item.chunk.metadata.source_release or "unknown",
                citation=item.chunk.metadata.citation,
                embedding_model=self._embedder.model,
                embedding_version=self._embedder.version,
                rank_score=max(0.0, min(1.0, (item.score + 1.0) / 2.0)),
            )
            for item in scored
        ]
        return ContextBundle(query=request.query, snippets=snippets)


def _read_local_text(reference: str) -> str:
    return Path(reference).read_text(encoding="utf-8")


def _split_text(text: str, max_characters: int) -> list[str]:
    paragraphs = [paragraph.strip() for paragraph in re.split(r"\n\s*\n", text) if paragraph.strip()]
    chunks: list[str] = []
    for paragraph in paragraphs:
        chunks.extend(
            paragraph[index : index + max_characters]
            for index in range(0, len(paragraph), max_characters)
        )
    return chunks


def _reference_metadata(reference: str) -> tuple[str, str, str | None]:
    if reference.upper().startswith("PMID:"):
        identifier = reference.split(":", 1)[1]
        return "PubMed", f"PMID:{identifier}", f"https://pubmed.ncbi.nlm.nih.gov/{identifier}/"
    if reference.upper().startswith("PMC"):
        identifier = reference.upper()
        return "PMC", identifier, f"https://pmc.ncbi.nlm.nih.gov/articles/{identifier}/"
    if reference.lower().startswith("doi:"):
        identifier = reference.split(":", 1)[1]
        return "DOI", reference, f"https://doi.org/{identifier}"
    return "Literature", reference, None


def _claim_for_marker(text: str, marker: str) -> str:
    for sentence in re.split(r"(?<=[.!?])\s+", text):
        if marker in sentence:
            return sentence.replace(marker, "").strip()
    return text.replace(marker, "").strip()


def _source_label(source_id: str | None) -> str:
    if source_id and source_id.startswith("PMID:"):
        return "PubMed"
    if source_id and source_id.startswith("PMC"):
        return "PMC"
    return "Local index"


def _embedding_key(model: str, version: str) -> str:
    return f"{model}@{version}"


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()
