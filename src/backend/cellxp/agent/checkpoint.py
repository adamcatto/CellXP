"""LangGraph checkpointer selection for local tests and durable deployments."""

from __future__ import annotations

from typing import Any

from langgraph.checkpoint.memory import InMemorySaver


def checkpointer_from_database_url(database_url: str | None) -> Any:
    """Return a Postgres saver in durable mode and an in-memory saver otherwise.

    The Postgres integration is imported lazily so contract/unit tests do not require a live
    database. Production fails loudly when durable mode is configured without its driver package.
    """
    if not database_url or not database_url.startswith(("postgresql://", "postgresql+psycopg://")):
        return InMemorySaver()
    try:
        import psycopg
        from langgraph.checkpoint.postgres import PostgresSaver
        from psycopg.rows import dict_row
    except ImportError as exc:  # pragma: no cover - production configuration guard
        raise RuntimeError(
            "durable checkpoints require langgraph-checkpoint-postgres"
        ) from exc
    dsn = database_url.replace("postgresql+psycopg://", "postgresql://", 1)
    connection = psycopg.connect(
        dsn, autocommit=True, prepare_threshold=0, row_factory=dict_row
    )
    saver = PostgresSaver(connection)
    saver.setup()
    return saver
