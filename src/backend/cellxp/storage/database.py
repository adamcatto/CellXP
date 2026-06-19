"""Database foundation — declarative base, cross-dialect column types, session factory.

The durable history (`relational_schema.md`) is **Postgres 16** in production (JSONB, native
enums, `uuid[]` arrays), but the ORM is kept dialect-portable so the suite can exercise the
round-trip contract (RS-3) against in-memory SQLite without a live Postgres. The Postgres-only
types degrade to portable JSON via `with_variant`; tables, keys, and the repository API are
identical on both.

Production wires an engine over `DATABASE_URL` (psycopg3); tests pass `sqlite://`. The session
factory here is synchronous — the async engine variant (`relational_schema.md` header) is a
drop-in over the same models and is deferred until the API server needs it.
"""

from __future__ import annotations

import enum
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import TypeVar

from sqlalchemy import JSON, DateTime, Enum, Uuid, create_engine
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

_E = TypeVar("_E", bound=enum.Enum)

# JSONB on Postgres; portable JSON elsewhere (SQLite tests). Used for params/inputs/summaries/
# confidence/provenance — structured-but-evolving shapes (`relational_schema.md` §3).
JSONType = JSON().with_variant(JSONB(), "postgresql")

# `uuid[]` on Postgres (e.g. messages.artifact_ids, review_items.evidence_ids); a JSON list of
# id strings elsewhere. Our ids are opaque strings (`domain/ids.py`).
UuidArray = JSON().with_variant(ARRAY(Uuid(as_uuid=False)), "postgresql")


def utc_now() -> datetime:
    """Timezone-aware UTC now — the Python-side default for `created_at`/domain timestamps."""
    return datetime.now(timezone.utc)


def pg_enum(enum_cls: type[_E]) -> Enum:
    """A SQLAlchemy `Enum` that stores the member **values** (e.g. ``"queued"``), mirroring
    `domain/enums.py`. On Postgres this is a native enum type; elsewhere a checked VARCHAR.
    New values are added by migration (`relational_schema.md` §3, RS-4)."""
    return Enum(
        enum_cls,
        values_callable=lambda e: [str(m.value) for m in e],
        name=enum_cls.__name__.lower(),
    )


# Reusable column-type aliases for timestamptz columns.
TimestampTZ = DateTime(timezone=True)


class Base(DeclarativeBase):
    """Declarative base for all CellXP history tables (`relational_schema.md` §4)."""


def make_engine(url: str, *, echo: bool = False):
    """Create a synchronous engine for `url` (psycopg3 Postgres in prod, sqlite:// in tests)."""
    return create_engine(url, echo=echo, future=True)


def make_session_factory(url: str, *, echo: bool = False) -> sessionmaker[Session]:
    """Bind a `sessionmaker` to a fresh engine for `url`."""
    return sessionmaker(bind=make_engine(url, echo=echo), expire_on_commit=False, future=True)


@contextmanager
def session_scope(factory: sessionmaker[Session]) -> Iterator[Session]:
    """Transactional session scope: commit on success, roll back on error, always close."""
    session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
