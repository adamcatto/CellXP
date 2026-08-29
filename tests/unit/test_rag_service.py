"""Unit coverage for the RAG service (X2, FR-20, RAG-1..5, PROV-1)."""

from __future__ import annotations

from cellxp.domain.enums import TaskStatus
from cellxp.services.base import ServiceOutcome
from cellxp.services.rag import (
    CitationExtractRequest,
    CitationRecord,
    CitationSet,
    ContextBundle,
    ContextRequest,
    ContextSnippet,
    IndexRequest,
    IndexResult,
    RagService,
    RetrievedChunk,
    RetrievedDocument,
    RetrieveRequest,
    SearchHit,
    SearchRequest,
    SearchResult,
)


class _MockBackend:
    def __init__(self, *, empty: bool = False) -> None:
        self.empty = empty

    def search(self, request: SearchRequest) -> SearchResult:
        return SearchResult(query=request.query, hits=[] if self.empty else [_hit()])

    def retrieve(self, request: RetrieveRequest) -> RetrievedDocument | None:
        if self.empty:
            return None
        return RetrievedDocument(
            source="PubMed",
            source_type="literature",
            source_id=request.identifier,
            title="Direct evidence",
            citation="PMID:123",
            storage_ref="objects/pmid-123.xml",
            chunks=[
                RetrievedChunk(
                    chunk_id="chunk-1",
                    text="direct supporting passage",
                    chunk_hash="sha256:abc",
                    source_id="PMID:123",
                    source_release="2026-06-01",
                    embedding_model="nomic-embed-text",
                )
            ],
        )

    def extract_citations(self, request: CitationExtractRequest) -> CitationSet:
        citations = (
            []
            if self.empty
            else [
                CitationRecord(
                    marker="[1]",
                    source="PubMed",
                    source_type="literature",
                    source_id="PMID:123",
                    citation="PMID:123",
                    claim="A direct claim",
                    confidence_score=0.9,
                )
            ]
        )
        return CitationSet(citations=citations)

    def index_documents(self, request: IndexRequest) -> IndexResult:
        return IndexResult(
            indexed_documents=0 if self.empty else 1,
            indexed_chunks=0 if self.empty else 4,
            namespace="public",
        )

    def answer_context(self, request: ContextRequest) -> ContextBundle:
        snippets = [] if self.empty else [_snippet()]
        return ContextBundle(query=request.query, snippets=snippets)


class _FailingBackend(_MockBackend):
    def search(self, request: SearchRequest) -> SearchResult:
        raise RuntimeError("source unavailable")


def _hit() -> SearchHit:
    return SearchHit(
        source="PubMed",
        source_type="literature",
        source_id="PMID:123",
        title="Direct evidence",
        citation="PMID:123",
        rank_score=0.91,
        source_release="2026-06-01",
        snippet="A direct supporting claim.",
    )


def _snippet() -> ContextSnippet:
    return ContextSnippet(
        text="A ranked supporting passage.",
        chunk_id="chunk-1",
        chunk_hash="sha256:abc",
        source="PubMed",
        source_type="literature",
        source_id="PMID:123",
        source_release="2026-06-01",
        citation="PMID:123",
        embedding_model="nomic-embed-text",
        embedding_version="1",
        rank_score=0.91,
    )


def test_no_backend_is_unsupported_with_step() -> None:
    result = RagService().search(SearchRequest(query="TP53"))
    assert result.outcome is ServiceOutcome.UNSUPPORTED
    assert result.steps and result.steps[0].status is TaskStatus.DONE


def test_unknown_organism_is_unsupported_before_backend() -> None:
    result = RagService(rag_backend=_MockBackend()).search(
        SearchRequest(query="gene", organism="Imaginary species")
    )
    assert result.outcome is ServiceOutcome.UNSUPPORTED
    assert result.steps


def test_mismatched_assembly_is_unsupported() -> None:
    result = RagService(rag_backend=_MockBackend()).answer_context(
        ContextRequest(
            query="gene",
            organism="Escherichia coli",
            assembly="GRCh38",
        )
    )
    assert result.outcome is ServiceOutcome.UNSUPPORTED


def test_search_success_emits_resolvable_evidence() -> None:
    result = RagService(rag_backend=_MockBackend()).search(SearchRequest(query="TP53"))
    assert result.outcome is ServiceOutcome.OK
    assert len(result.evidence) == 1
    provenance = result.evidence[0].provenance
    assert provenance.tool == "PubMed"
    assert provenance.tool_version == "2026-06-01"
    assert provenance.inputs["query"] == "TP53"
    assert provenance.timestamp


def test_search_no_hits_is_empty_not_failure() -> None:
    result = RagService(rag_backend=_MockBackend(empty=True)).search(SearchRequest(query="none"))
    assert result.outcome is ServiceOutcome.EMPTY
    assert result.steps
    assert not result.evidence


def test_backend_failure_does_not_fabricate_citations() -> None:
    result = RagService(rag_backend=_FailingBackend()).search(SearchRequest(query="TP53"))
    assert result.outcome is ServiceOutcome.FAILURE
    assert result.error and result.error.kind == "BackendError"
    assert not result.evidence and not result.artifacts
    assert result.steps[0].status is TaskStatus.FAILED


def test_retrieve_emits_document_artifact_with_storage_ref() -> None:
    result = RagService(rag_backend=_MockBackend()).retrieve(
        RetrieveRequest(source="PubMed", identifier="PMID:123")
    )
    assert result.outcome is ServiceOutcome.OK
    assert result.artifacts[0].storage_ref == "objects/pmid-123.xml"
    assert result.artifacts[0].evidence_ids == [result.evidence[0].id]


def test_extract_citations_builds_evidence_map_and_artifact() -> None:
    result = RagService(rag_backend=_MockBackend()).extract_citations(
        CitationExtractRequest(text="A direct claim [1].")
    )
    assert result.outcome is ServiceOutcome.OK
    assert result.value is not None
    assert result.value.citation_map["[1]"] == result.evidence[0].id
    assert result.artifacts[0].evidence_ids == [result.evidence[0].id]


def test_context_preserves_chunk_and_embedding_provenance() -> None:
    result = RagService(rag_backend=_MockBackend()).answer_context(
        ContextRequest(query="TP53", organism="Homo sapiens", assembly="GRCh38")
    )
    assert result.outcome is ServiceOutcome.OK
    assert result.value is not None
    assert result.value.citation_map["[1]"] == result.evidence[0].id
    provenance = result.evidence[0].provenance
    assert provenance.inputs["chunk_id"] == "chunk-1"
    assert provenance.inputs["embedding_model"] == "nomic-embed-text"
    assert provenance.output_hash == "sha256:abc"


def test_index_empty_is_empty_with_provenance_step() -> None:
    result = RagService(rag_backend=_MockBackend(empty=True)).index_documents(
        IndexRequest(embedding_model="nomic-embed-text")
    )
    assert result.outcome is ServiceOutcome.EMPTY
    assert result.steps


def test_every_operation_emits_at_least_one_step() -> None:
    service = RagService(rag_backend=_MockBackend())
    results = [
        service.search(SearchRequest(query="TP53")),
        service.retrieve(RetrieveRequest(source="PubMed", identifier="PMID:123")),
        service.extract_citations(CitationExtractRequest(text="claim")),
        service.index_documents(IndexRequest(embedding_model="nomic-embed-text")),
        service.answer_context(ContextRequest(query="TP53")),
    ]
    assert all(result.steps for result in results)
