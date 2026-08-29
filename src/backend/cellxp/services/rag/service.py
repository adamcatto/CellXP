"""Literature and database retrieval service (X2, FR-20, RAG-1..5)."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, Literal, TypeVar

from cellxp.agent.state import RunError, Step
from cellxp.domain.artifacts import ArtifactRef
from cellxp.domain.clock import utc_now_iso
from cellxp.domain.enums import ArtifactType, ConfidenceBand, SourceKind, TaskStatus
from cellxp.domain.evidence import Confidence, EvidenceItem, Provenance
from cellxp.domain.ids import new_id
from cellxp.services.base import Service, ServiceResult
from cellxp.services.reference.genome import ASSEMBLY_CATALOG, SPECIES_PROFILES
from cellxp.services.registry import registry

from .schemas import (
    CitationExtractRequest,
    CitationRecord,
    CitationSet,
    ContextBundle,
    ContextRequest,
    ContextSnippet,
    IndexRequest,
    IndexResult,
    RagBackend,
    RetrievalContext,
    RetrievedDocument,
    RetrieveRequest,
    SearchHit,
    SearchRequest,
    SearchResult,
)

T = TypeVar("T")


@registry.register
class RagService(Service):
    """Normalize configured RAG backends into provenance-bearing service results."""

    name = "rag"

    def __init__(self, *, rag_backend: RagBackend | None = None) -> None:
        self._backend = rag_backend

    def search(self, request: SearchRequest) -> ServiceResult[SearchResult]:
        return self._call(
            "search",
            request,
            lambda: self._backend.search(request),  # type: ignore[union-attr]
            evidence_builder=lambda value, finished: [
                _evidence_from_hit(hit, request.query, finished) for hit in value.hits
            ],
            is_empty=lambda value: value is None or not value.hits,
        )

    def retrieve(self, request: RetrieveRequest) -> ServiceResult[RetrievedDocument]:
        return self._call(
            "retrieve",
            request,
            lambda: self._backend.retrieve(request),  # type: ignore[union-attr]
            evidence_builder=lambda value, finished: [_evidence_from_document(value, finished)],
            artifacts_builder=lambda value, evidence: (
                [
                    ArtifactRef(
                        type=ArtifactType.FILE,
                        title=value.title,
                        storage_ref=value.storage_ref,
                        summary={"source": value.source, "source_id": value.source_id},
                        evidence_ids=[item.id for item in evidence],
                    )
                ]
                if value.storage_ref
                else []
            ),
            is_empty=lambda value: value is None,
        )

    def extract_citations(self, request: CitationExtractRequest) -> ServiceResult[CitationSet]:
        return self._call(
            "extract_citations",
            request,
            lambda: self._backend.extract_citations(request),  # type: ignore[union-attr]
            normalize=_normalize_citation_set,
            evidence_builder=lambda value, finished: [
                _evidence_from_citation(citation, finished) for citation in value.citations
            ],
            artifacts_builder=_citation_artifacts,
            is_empty=lambda value: value is None or not value.citations,
        )

    def index_documents(self, request: IndexRequest) -> ServiceResult[IndexResult]:
        return self._call(
            "index_documents",
            request,
            lambda: self._backend.index_documents(request),  # type: ignore[union-attr]
            is_empty=lambda value: value is None or value.indexed_documents == 0,
            weight="heavy",
        )

    def answer_context(self, request: ContextRequest) -> ServiceResult[ContextBundle]:
        return self._call(
            "answer_context",
            request,
            lambda: self._backend.answer_context(request),  # type: ignore[union-attr]
            normalize=_normalize_context,
            evidence_builder=lambda value, finished: [
                _evidence_from_snippet(snippet, request.query, finished)
                for snippet in value.snippets
            ],
            artifacts_builder=lambda value, evidence: [
                ArtifactRef(
                    type=ArtifactType.REPORT,
                    title="RAG citation context",
                    summary={"citation_map": value.citation_map, "count": len(value.snippets)},
                    evidence_ids=[item.id for item in evidence],
                )
            ],
            is_empty=lambda value: value is None or not value.snippets,
            weight="heavy",
        )

    def _call(
        self,
        name: str,
        request: RetrievalContext,
        operation: Callable[[], T | None],
        *,
        normalize: Callable[[T], T] | None = None,
        evidence_builder: Callable[[T, str], list[EvidenceItem]] | None = None,
        artifacts_builder: Callable[[T, list[EvidenceItem]], list[ArtifactRef]] | None = None,
        is_empty: Callable[[T | None], bool] | None = None,
        weight: Literal["light", "heavy"] = "light",
    ) -> ServiceResult[T]:
        started = utc_now_iso()
        unsupported = _unsupported_context(request)
        if unsupported is not None:
            return ServiceResult.unsupported(
                unsupported, steps=[_done_step(name, started, weight=weight)]
            )
        if self._backend is None:
            return ServiceResult.unsupported(
                f"{name} requires a RAG backend; none is configured",
                steps=[_done_step(name, started, weight=weight)],
            )
        try:
            value = operation()
        except Exception as exc:  # noqa: BLE001
            return ServiceResult.failed(
                RunError(kind="BackendError", message=str(exc)),
                steps=[_failed_step(name, started, str(exc), weight=weight)],
            )
        if is_empty is not None and is_empty(value):
            return ServiceResult.empty(
                f"{name} completed with no results",
                steps=[_done_step(name, started, weight=weight)],
            )
        assert value is not None
        if normalize is not None:
            value = normalize(value)
        finished = utc_now_iso()
        evidence = evidence_builder(value, finished) if evidence_builder else []
        artifacts = artifacts_builder(value, evidence) if artifacts_builder else []
        return ServiceResult.succeeded(
            value,
            steps=[_done_step(name, started, finished=finished, weight=weight)],
            evidence=evidence,
            artifacts=artifacts,
        )


def _unsupported_context(request: RetrievalContext) -> str | None:
    if request.organism is not None and request.organism not in SPECIES_PROFILES:
        return f"organism {request.organism!r} not in species catalog"
    if request.assembly is not None:
        assembly = ASSEMBLY_CATALOG.get(request.assembly)
        if assembly is None:
            return f"assembly {request.assembly!r} not in reference catalog"
        if request.organism is not None and assembly.organism != request.organism:
            return f"assembly {request.assembly!r} does not belong to {request.organism!r}"
    return None


def _source_kind(value: str) -> SourceKind:
    return SourceKind.LITERATURE if value == "literature" else SourceKind.DATABASE


def _confidence(score: float) -> Confidence:
    band = (
        ConfidenceBand.HIGH
        if score >= 0.8
        else ConfidenceBand.MEDIUM
        if score >= 0.5
        else ConfidenceBand.LOW
    )
    return Confidence(band=band, score=score, basis="retrieval rank and source directness")


def _provenance(
    *,
    source: str,
    source_id: str,
    citation: str,
    inputs: dict[str, Any],
    timestamp: str,
    source_release: str | None = None,
    output_hash: str | None = None,
) -> Provenance:
    return Provenance(
        tool=source,
        tool_version=source_release or "unknown",
        inputs=inputs,
        citations=[citation, source_id],
        timestamp=timestamp,
        output_hash=output_hash,
    )


def _evidence_from_hit(hit: SearchHit, query: str, timestamp: str) -> EvidenceItem:
    return EvidenceItem(
        source=hit.source,
        source_kind=_source_kind(hit.source_type),
        claim=hit.snippet or hit.title,
        value={"source_id": hit.source_id, "title": hit.title, "url": hit.url},
        confidence=_confidence(hit.rank_score),
        provenance=_provenance(
            source=hit.source,
            source_id=hit.source_id,
            citation=hit.citation,
            inputs={"query": query, "rank_score": hit.rank_score},
            timestamp=timestamp,
            source_release=hit.source_release,
        ),
    )


def _evidence_from_document(document: RetrievedDocument, timestamp: str) -> EvidenceItem:
    return EvidenceItem(
        source=document.source,
        source_kind=_source_kind(document.source_type),
        claim=f"Retrieved source: {document.title}",
        value={"source_id": document.source_id, "url": document.url},
        confidence=Confidence(band=ConfidenceBand.HIGH, basis="direct source retrieval"),
        provenance=_provenance(
            source=document.source,
            source_id=document.source_id,
            citation=document.citation,
            inputs={"chunk_ids": [chunk.chunk_id for chunk in document.chunks]},
            timestamp=timestamp,
            output_hash=document.chunks[0].chunk_hash if document.chunks else None,
        ),
    )


def _evidence_from_citation(citation: CitationRecord, timestamp: str) -> EvidenceItem:
    assert citation.evidence_id is not None
    return EvidenceItem(
        id=citation.evidence_id,
        source=citation.source,
        source_kind=_source_kind(citation.source_type),
        claim=citation.claim,
        value={"source_id": citation.source_id, "url": citation.url},
        confidence=_confidence(citation.confidence_score),
        provenance=_provenance(
            source=citation.source,
            source_id=citation.source_id,
            citation=citation.citation,
            inputs={"marker": citation.marker},
            timestamp=timestamp,
        ),
    )


def _evidence_from_snippet(snippet: ContextSnippet, query: str, timestamp: str) -> EvidenceItem:
    assert snippet.evidence_id is not None
    return EvidenceItem(
        id=snippet.evidence_id,
        source=snippet.source,
        source_kind=_source_kind(snippet.source_type),
        claim=snippet.text,
        value={"chunk_id": snippet.chunk_id, "source_id": snippet.source_id},
        confidence=_confidence(snippet.rank_score),
        provenance=_provenance(
            source=snippet.source,
            source_id=snippet.source_id,
            citation=snippet.citation,
            inputs={
                "query": query,
                "chunk_id": snippet.chunk_id,
                "embedding_model": snippet.embedding_model,
                "embedding_version": snippet.embedding_version,
            },
            timestamp=timestamp,
            source_release=snippet.source_release,
            output_hash=snippet.chunk_hash,
        ),
    )


def _normalize_citation_set(value: CitationSet) -> CitationSet:
    citations = [
        citation if citation.evidence_id else citation.model_copy(update={"evidence_id": new_id()})
        for citation in value.citations
    ]
    return value.model_copy(
        update={
            "citations": citations,
            "citation_map": {citation.marker: citation.evidence_id for citation in citations},
        }
    )


def _normalize_context(value: ContextBundle) -> ContextBundle:
    snippets = [
        snippet if snippet.evidence_id else snippet.model_copy(update={"evidence_id": new_id()})
        for snippet in value.snippets
    ]
    return value.model_copy(
        update={
            "snippets": snippets,
            "citation_map": {
                f"[{index}]": snippet.evidence_id for index, snippet in enumerate(snippets, 1)
            },
        }
    )


def _citation_artifacts(value: CitationSet, evidence: list[EvidenceItem]) -> list[ArtifactRef]:
    return [
        ArtifactRef(
            type=ArtifactType.REPORT,
            title="Citation set",
            summary={"citation_map": value.citation_map, "count": len(value.citations)},
            evidence_ids=[item.id for item in evidence],
        )
    ]


def _done_step(
    name: str,
    started: str,
    *,
    finished: str | None = None,
    weight: Literal["light", "heavy"] = "light",
) -> Step:
    return Step(
        name=name,
        tool="rag",
        weight=weight,
        status=TaskStatus.DONE,
        started_at=started,
        finished_at=finished or utc_now_iso(),
    )


def _failed_step(
    name: str,
    started: str,
    error: str,
    *,
    weight: Literal["light", "heavy"] = "light",
) -> Step:
    return Step(
        name=name,
        tool="rag",
        weight=weight,
        status=TaskStatus.FAILED,
        started_at=started,
        finished_at=utc_now_iso(),
        error=error,
    )
