"""Persistence layer — durable history + object store (`specs/data/`).

The repository (`repositories.py`) is the sole writer of run history; services produce
provenance-bearing results and the repository persists them (`provenance_model.md`). The
relational schema (`models.py`) mirrors `AgentState`; large/opaque payloads live in the object
store (`object_store.py`), Postgres holding only their keys.
"""

from __future__ import annotations

from .database import Base, make_engine, make_session_factory, session_scope
from .object_store import (
    FilesystemObjectStore,
    ObjectRef,
    ObjectStore,
    S3ObjectStore,
    object_store_from_url,
)
from .repositories import AppendOnlyError, StateRepository

__all__ = [
    "AppendOnlyError",
    "Base",
    "FilesystemObjectStore",
    "ObjectRef",
    "ObjectStore",
    "S3ObjectStore",
    "StateRepository",
    "make_engine",
    "make_session_factory",
    "object_store_from_url",
    "session_scope",
]
