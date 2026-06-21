"""Local SQLite vector index for citation-bearing RAG chunks.

The implementation intentionally uses only the Python standard library.  It is suitable for
local development and small corpora; deployments can inject another ``VectorIndex`` implementation
without changing the RAG service.
"""

from __future__ import annotations

import json
import math
import sqlite3
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

from pydantic import BaseModel, Field, field_validator


class RagChunkMetadata(BaseModel):
    source_kind: str
    citation: str
    embedding_model: str
    ingested_at: str
    source_id: str | None = None
    source_release: str | None = None
    title: str | None = None
    section: str | None = None
    organism: str | None = None
    published: str | None = None
    url: str | None = None

    @field_validator("citation", "embedding_model")
    @classmethod
    def _required_provenance(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("citation and embedding_model must be non-empty")
        return value.strip()


class RagVectorChunk(BaseModel):
    id: str
    namespace: str
    text: str
    embedding: list[float] = Field(min_length=1)
    metadata: RagChunkMetadata


class RagScoredChunk(BaseModel):
    chunk: RagVectorChunk
    score: float


@runtime_checkable
class RagVectorIndex(Protocol):
    def upsert(self, chunks: Sequence[RagVectorChunk]) -> None: ...

    def query(
        self,
        embedding: Sequence[float],
        *,
        embedding_model: str,
        k: int,
        namespace: str,
        filters: Mapping[str, str] | None = None,
    ) -> list[RagScoredChunk]: ...

    def delete(
        self,
        ids: Sequence[str] | None = None,
        *,
        namespace: str,
        filters: Mapping[str, str] | None = None,
    ) -> int: ...


class SQLiteRagVectorIndex:
    """Persistent local cosine index backed by SQLite.

    Vector scoring is performed in-process. This favors a dependency-free, deterministic local
    backend over scale; a managed implementation can satisfy the same protocol in production.
    """

    def __init__(self, path: str | Path = ":memory:") -> None:
        self._connection = sqlite3.connect(str(path), check_same_thread=False)
        self._connection.row_factory = sqlite3.Row
        self._connection.execute(
            """
            CREATE TABLE IF NOT EXISTS rag_vectors (
                namespace TEXT NOT NULL,
                id TEXT NOT NULL,
                text TEXT NOT NULL,
                embedding TEXT NOT NULL,
                embedding_model TEXT NOT NULL,
                dimensions INTEGER NOT NULL,
                metadata TEXT NOT NULL,
                PRIMARY KEY (namespace, id)
            )
            """
        )
        self._connection.commit()

    def close(self) -> None:
        self._connection.close()

    def upsert(self, chunks: Sequence[RagVectorChunk]) -> None:
        if not chunks:
            return
        namespace_models: dict[str, str] = {}
        for chunk in chunks:
            expected = namespace_models.setdefault(
                chunk.namespace, self._namespace_model(chunk.namespace) or chunk.metadata.embedding_model
            )
            if chunk.metadata.embedding_model != expected:
                raise ValueError(
                    f"namespace {chunk.namespace!r} uses embedding model {expected!r}; "
                    f"cannot insert {chunk.metadata.embedding_model!r} without re-embedding"
                )
            dimensions = self._namespace_dimensions(chunk.namespace)
            if dimensions is not None and dimensions != len(chunk.embedding):
                raise ValueError(
                    f"namespace {chunk.namespace!r} uses {dimensions} dimensions, "
                    f"received {len(chunk.embedding)}"
                )

        rows = [
            (
                chunk.namespace,
                chunk.id,
                chunk.text,
                json.dumps(chunk.embedding),
                chunk.metadata.embedding_model,
                len(chunk.embedding),
                chunk.metadata.model_dump_json(),
            )
            for chunk in chunks
        ]
        with self._connection:
            self._connection.executemany(
                """
                INSERT INTO rag_vectors
                    (namespace, id, text, embedding, embedding_model, dimensions, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(namespace, id) DO UPDATE SET
                    text=excluded.text,
                    embedding=excluded.embedding,
                    embedding_model=excluded.embedding_model,
                    dimensions=excluded.dimensions,
                    metadata=excluded.metadata
                """,
                rows,
            )

    def query(
        self,
        embedding: Sequence[float],
        *,
        embedding_model: str,
        k: int,
        namespace: str,
        filters: Mapping[str, str] | None = None,
    ) -> list[RagScoredChunk]:
        if k < 1:
            raise ValueError("k must be at least 1")
        model = self._namespace_model(namespace)
        if model is not None and model != embedding_model:
            raise ValueError(
                f"namespace {namespace!r} uses embedding model {model!r}, not {embedding_model!r}"
            )
        dimensions = self._namespace_dimensions(namespace)
        if dimensions is not None and dimensions != len(embedding):
            raise ValueError(
                f"namespace {namespace!r} uses {dimensions} dimensions, received {len(embedding)}"
            )

        rows = self._connection.execute(
            "SELECT * FROM rag_vectors WHERE namespace = ? AND embedding_model = ?",
            (namespace, embedding_model),
        ).fetchall()
        scored: list[RagScoredChunk] = []
        for row in rows:
            metadata = RagChunkMetadata.model_validate_json(row["metadata"])
            if filters and not _metadata_matches(metadata, filters):
                continue
            chunk = RagVectorChunk(
                id=row["id"],
                namespace=row["namespace"],
                text=row["text"],
                embedding=json.loads(row["embedding"]),
                metadata=metadata,
            )
            scored.append(
                RagScoredChunk(chunk=chunk, score=_cosine(embedding, chunk.embedding))
            )
        return sorted(scored, key=lambda item: (-item.score, item.chunk.id))[:k]

    def delete(
        self,
        ids: Sequence[str] | None = None,
        *,
        namespace: str,
        filters: Mapping[str, str] | None = None,
    ) -> int:
        rows = self._connection.execute(
            "SELECT id, metadata FROM rag_vectors WHERE namespace = ?", (namespace,)
        ).fetchall()
        wanted = set(ids) if ids is not None else None
        selected = [
            row["id"]
            for row in rows
            if (wanted is None or row["id"] in wanted)
            and (not filters or _metadata_matches(RagChunkMetadata.model_validate_json(row["metadata"]), filters))
        ]
        with self._connection:
            self._connection.executemany(
                "DELETE FROM rag_vectors WHERE namespace = ? AND id = ?",
                [(namespace, chunk_id) for chunk_id in selected],
            )
        return len(selected)

    def _namespace_model(self, namespace: str) -> str | None:
        row = self._connection.execute(
            "SELECT embedding_model FROM rag_vectors WHERE namespace = ? LIMIT 1", (namespace,)
        ).fetchone()
        return str(row[0]) if row else None

    def _namespace_dimensions(self, namespace: str) -> int | None:
        row = self._connection.execute(
            "SELECT dimensions FROM rag_vectors WHERE namespace = ? LIMIT 1", (namespace,)
        ).fetchone()
        return int(row[0]) if row else None


def _metadata_matches(metadata: RagChunkMetadata, filters: Mapping[str, str]) -> bool:
    values: dict[str, Any] = metadata.model_dump()
    return all(str(values.get(key)) == value for key, value in filters.items())


def _cosine(left: Sequence[float], right: Sequence[float]) -> float:
    if len(left) != len(right):
        raise ValueError("vectors must have equal dimensions")
    dot = sum(a * b for a, b in zip(left, right, strict=True))
    left_norm = math.sqrt(sum(value * value for value in left))
    right_norm = math.sqrt(sum(value * value for value in right))
    if left_norm == 0 or right_norm == 0:
        return 0.0
    return dot / (left_norm * right_norm)
