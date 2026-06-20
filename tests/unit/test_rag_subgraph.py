"""Unit coverage for the RAG capability subgraph (X2, FR-20, FR-24)."""

from __future__ import annotations

from cellxp.agent.state import AgentState, ExecutionCursor, NormalizedInputs, Subtask
from cellxp.agent.subgraphs.rag import build_subgraph
from cellxp.domain.enums import SubtaskType, TaskStatus
from cellxp.services.rag import ContextBundle, ContextRequest, ContextSnippet, RagService
from cellxp.services.rag.schemas import (
    CitationExtractRequest,
    CitationSet,
    IndexRequest,
    IndexResult,
    RetrieveRequest,
    RetrievedDocument,
    SearchRequest,
    SearchResult,
)


class _ContextBackend:
    def answer_context(self, request: ContextRequest) -> ContextBundle:
        return ContextBundle(
            query=request.query,
            snippets=[
                ContextSnippet(
                    text="Supported by a primary paper.",
                    chunk_id="c1",
                    chunk_hash="sha256:c1",
                    source="PubMed",
                    source_type="literature",
                    source_id="PMID:1",
                    source_release="2026-01",
                    citation="PMID:1",
                    embedding_model="local-embed",
                    rank_score=0.9,
                )
            ],
        )

    def search(self, request: SearchRequest) -> SearchResult:
        return SearchResult(query=request.query)

    def retrieve(self, request: RetrieveRequest) -> RetrievedDocument | None:
        return None

    def extract_citations(self, request: CitationExtractRequest) -> CitationSet:
        return CitationSet()

    def index_documents(self, request: IndexRequest) -> IndexResult:
        return IndexResult()


class _FailingContextBackend(_ContextBackend):
    def answer_context(self, request: ContextRequest) -> ContextBundle:
        raise RuntimeError("retriever offline")


def _state(
    *,
    query: str | None = "ground TP53",
    organism: str | None = "Homo sapiens",
    assembly: str | None = "GRCh38",
) -> AgentState:
    subtask = Subtask(
        type=SubtaskType.RAG,
        capability="rag",
        status=TaskStatus.RUNNING,
        inputs={"claim": query} if query else {},
    )
    return AgentState(
        subtasks=[subtask.model_dump()],
        cursor=ExecutionCursor(active_subtask_id=subtask.id).model_dump(),
        normalized_inputs=NormalizedInputs(organism=organism, assembly=assembly).model_dump(),
        steps=[],
        evidence=[],
        artifacts=[],
        errors=[],
    )


def _active_status(result: dict[str, object]) -> TaskStatus:
    subtasks = result["subtasks"]
    assert isinstance(subtasks, list)
    return Subtask.model_validate(subtasks[0]).status


def test_no_query_fails_with_step_and_error() -> None:
    result = build_subgraph()(_state(query=None, organism=None, assembly=None))
    assert _active_status(result) is TaskStatus.FAILED
    assert result["steps"] and result["errors"]


def test_valid_path_emits_evidence_artifact_and_done_steps() -> None:
    node = build_subgraph(rag_service=RagService(rag_backend=_ContextBackend()))
    result = node(_state())
    assert _active_status(result) is TaskStatus.DONE
    assert result["evidence"] and result["artifacts"]
    steps = result["steps"]
    assert isinstance(steps, list)
    assert all(step.status is TaskStatus.DONE for step in steps)
    assert {step.name for step in steps} >= {"formulate_queries", "retrieve_rank_and_extract"}


def test_invalid_reference_fails_before_retrieval() -> None:
    result = build_subgraph(rag_service=RagService(rag_backend=_ContextBackend()))(
        _state(organism="Escherichia coli", assembly="GRCh38")
    )
    assert _active_status(result) is TaskStatus.FAILED
    assert result["errors"]
    assert all(step.name != "answer_context" for step in result["steps"])


def test_no_backend_is_honest_non_error_completion() -> None:
    result = build_subgraph()(_state())
    assert _active_status(result) is TaskStatus.DONE
    assert not result["evidence"] and not result["artifacts"]
    assert result["steps"]


def test_backend_failure_marks_subtask_failed_with_steps() -> None:
    node = build_subgraph(rag_service=RagService(rag_backend=_FailingContextBackend()))
    result = node(_state())
    assert _active_status(result) is TaskStatus.FAILED
    assert result["steps"] and result["errors"]
    assert any(step.status is TaskStatus.FAILED for step in result["steps"])


def test_no_active_subtask_returns_empty() -> None:
    state = AgentState(
        subtasks=[],
        cursor=ExecutionCursor().model_dump(),
        normalized_inputs=NormalizedInputs().model_dump(),
    )
    assert build_subgraph()(state) == {}
