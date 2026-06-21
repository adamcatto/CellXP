"""Deterministic contract tests for the local RAG vector index (VI-1..6)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from cellxp.storage.rag_vector_index import (
    RagChunkMetadata,
    RagVectorChunk,
    SQLiteRagVectorIndex,
)


def _chunk(
    chunk_id: str,
    embedding: list[float],
    *,
    model: str = "test-embed:1",
    organism: str = "Homo sapiens",
) -> RagVectorChunk:
    return RagVectorChunk(
        id=chunk_id,
        namespace="literature",
        text=f"passage {chunk_id}",
        embedding=embedding,
        metadata=RagChunkMetadata(
            source_kind="literature",
            citation=f"PMID:{chunk_id}",
            source_id=f"PMID:{chunk_id}",
            embedding_model=model,
            ingested_at="2026-06-21T00:00:00Z",
            organism=organism,
        ),
    )


def test_requires_citation_and_embedding_provenance() -> None:
    with pytest.raises(ValidationError):
        RagChunkMetadata(
            source_kind="literature", citation="", embedding_model="model", ingested_at="now"
        )


def test_upsert_is_idempotent_and_query_ranks_cosine_similarity() -> None:
    index = SQLiteRagVectorIndex()
    index.upsert([_chunk("2", [0.0, 1.0]), _chunk("1", [1.0, 0.0])])
    index.upsert([_chunk("1", [0.8, 0.2])])

    hits = index.query(
        [1.0, 0.0], embedding_model="test-embed:1", k=10, namespace="literature"
    )

    assert [hit.chunk.id for hit in hits] == ["1", "2"]
    assert len(hits) == 2
    assert hits[0].chunk.metadata.citation == "PMID:1"


def test_namespace_model_and_dimensions_are_guarded() -> None:
    index = SQLiteRagVectorIndex()
    index.upsert([_chunk("1", [1.0, 0.0])])

    with pytest.raises(ValueError, match="without re-embedding"):
        index.upsert([_chunk("2", [1.0, 0.0], model="different:2")])
    with pytest.raises(ValueError, match="not 'different:2'"):
        index.query(
            [1.0, 0.0], embedding_model="different:2", k=1, namespace="literature"
        )
    with pytest.raises(ValueError, match="dimensions"):
        index.query(
            [1.0], embedding_model="test-embed:1", k=1, namespace="literature"
        )


def test_filters_and_delete_are_namespace_scoped() -> None:
    index = SQLiteRagVectorIndex()
    index.upsert(
        [
            _chunk("human", [1.0, 0.0]),
            _chunk("mouse", [1.0, 0.0], organism="Mus musculus"),
        ]
    )

    hits = index.query(
        [1.0, 0.0],
        embedding_model="test-embed:1",
        k=5,
        namespace="literature",
        filters={"organism": "Mus musculus"},
    )
    deleted = index.delete(
        namespace="literature", filters={"organism": "Mus musculus"}
    )

    assert [hit.chunk.id for hit in hits] == ["mouse"]
    assert deleted == 1
    assert [
        hit.chunk.id
        for hit in index.query(
            [1.0, 0.0], embedding_model="test-embed:1", k=5, namespace="literature"
        )
    ] == ["human"]


def test_sqlite_index_persists_between_instances(tmp_path) -> None:
    path = tmp_path / "rag.sqlite3"
    first = SQLiteRagVectorIndex(path)
    first.upsert([_chunk("1", [1.0, 0.0])])
    first.close()

    second = SQLiteRagVectorIndex(path)
    hits = second.query(
        [1.0, 0.0], embedding_model="test-embed:1", k=1, namespace="literature"
    )
    second.close()

    assert hits[0].chunk.id == "1"
