"""Network-free composition tests for the local RAG backend (RAG-1..5, VI-3)."""

from __future__ import annotations

from collections.abc import Sequence

from cellxp.services.rag import (
    CitationExtractRequest,
    ContextRequest,
    IndexDocument,
    IndexRequest,
    LocalRagBackend,
)
from cellxp.storage.rag_vector_index import SQLiteRagVectorIndex


class _Embedder:
    model = "test-embed"
    version = "1"

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        return [
            [float("variant" in text.casefold()), float("protein" in text.casefold())]
            for text in texts
        ]


class _NoNetworkLiterature:
    def search_pubmed(self, request):  # pragma: no cover - not used by these tests
        raise AssertionError("network adapter should not be called")

    def retrieve(self, source, identifier):  # pragma: no cover - not used by these tests
        raise AssertionError("network adapter should not be called")


def _backend(documents: dict[str, str] | None = None) -> LocalRagBackend:
    documents = documents or {}
    return LocalRagBackend(
        literature=_NoNetworkLiterature(),  # type: ignore[arg-type]
        vector_index=SQLiteRagVectorIndex(),
        embedder=_Embedder(),
        text_loader=documents.__getitem__,
        chunk_characters=100,
    )


def test_index_and_context_round_trip_preserves_citation() -> None:
    backend = _backend(
        {"doc:1": "The variant changes transcription.\n\nProtein abundance is unchanged."}
    )
    indexed = backend.index_documents(
        IndexRequest(
            embedding_model="test-embed",
            embedding_version="1",
            organism="Homo sapiens",
            documents=[
                IndexDocument(
                    source="PubMed",
                    source_type="literature",
                    source_id="PMID:123",
                    source_release="2025-06",
                    text_ref="doc:1",
                    namespace="literature",
                )
            ],
        )
    )
    context = backend.answer_context(
        ContextRequest(query="variant", organism="Homo sapiens", max_snippets=1)
    )

    assert indexed.indexed_chunks == 2
    assert context.snippets[0].citation == "PMID:123"
    assert context.snippets[0].source_release == "2025-06"
    assert context.snippets[0].embedding_model == "test-embed"
    assert context.snippets[0].rank_score == 1.0


def test_private_document_requires_isolated_namespace() -> None:
    backend = _backend({"private": "private user content"})

    try:
        backend.index_documents(
            IndexRequest(
                embedding_model="test-embed",
                documents=[
                    IndexDocument(
                        source="upload",
                        source_type="database",
                        source_id="upload:1",
                        source_release="1",
                        text_ref="private",
                        namespace="literature",
                        private=True,
                    )
                ],
            )
        )
    except ValueError as error:
        assert "private/ or session/" in str(error)
    else:  # pragma: no cover
        raise AssertionError("private corpus was accepted in a public namespace")


def test_citation_extraction_only_resolves_supplied_references() -> None:
    result = _backend().extract_citations(
        CitationExtractRequest(
            text="Variants affect expression [1]. Unreferenced claim [2].",
            document_refs=["PMID:123"],
        )
    )

    assert len(result.citations) == 1
    assert result.citations[0].marker == "[1]"
    assert result.citations[0].source_id == "PMID:123"
    assert result.citations[0].url == "https://pubmed.ncbi.nlm.nih.gov/123/"


def test_embedding_model_mismatch_is_rejected_before_indexing() -> None:
    backend = _backend({"doc": "variant"})
    try:
        backend.index_documents(
            IndexRequest(
                embedding_model="other",
                documents=[
                    IndexDocument(
                        source="PubMed",
                        source_type="literature",
                        source_id="PMID:1",
                        source_release="1",
                        text_ref="doc",
                        namespace="literature",
                    )
                ],
            )
        )
    except ValueError as error:
        assert "configured embedder" in str(error)
    else:  # pragma: no cover
        raise AssertionError("embedding model mismatch was accepted")
