"""ORM models — the durable mirror of `AgentState` (`relational_schema.md` §4).

One table per persisted state substructure, joined by the universal `run_id` FK. Large/opaque
payloads are **not** stored here — only their object-store key (`*_ref`/`storage_ref`,
`object_storage.md`, RS-5). Append-only tables (`messages`, `steps`, `evidence_items`,
`artifacts`, `run_errors`) carry `__append_only__ = True`; the repository layer enforces
insert-only semantics and routes corrections through `supersedes` (RS-2, PROV-3).

Enum columns mirror `domain/enums.py` by value (RS-4). IDs are opaque strings (`domain/ids.py`,
ULID/UUIDv7 target) stored as `uuid`.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, ForeignKey, Index, Integer, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from cellxp.domain.enums import (
    ArtifactType,
    ReviewDecision,
    RunStatus,
    SourceKind,
    SubtaskType,
    TaskStatus,
)
from cellxp.domain.ids import new_id

from .database import Base, JSONType, TimestampTZ, UuidArray, pg_enum, utc_now


def _id_col() -> Mapped[str]:
    return mapped_column(Uuid(as_uuid=False), primary_key=True, default=new_id)


def _run_fk() -> Mapped[str]:
    return mapped_column(Uuid(as_uuid=False), ForeignKey("runs.id"), nullable=False, index=True)


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = _id_col()
    external_id: Mapped[str | None] = mapped_column(String, unique=True)  # auth subject
    display_name: Mapped[str | None] = mapped_column(String)
    role: Mapped[str | None] = mapped_column(String)  # analyst | reviewer/PI (review perms)
    created_at: Mapped[datetime] = mapped_column(TimestampTZ, default=utc_now)


class WorkspaceSession(Base):
    """Persistent typed workspace (`session_types.md`); table ``sessions``."""

    __tablename__ = "sessions"

    id: Mapped[str] = _id_col()
    user_id: Mapped[str | None] = mapped_column(Uuid(as_uuid=False), ForeignKey("users.id"))
    type: Mapped[str | None] = mapped_column(String)  # variant_interpretation | genome_editing | …
    title: Mapped[str | None] = mapped_column(String)
    defaults: Mapped[dict[str, Any]] = mapped_column(JSONType, default=dict)  # organism/assembly/…
    memory: Mapped[dict[str, Any]] = mapped_column(JSONType, default=dict)  # carried context
    created_at: Mapped[datetime] = mapped_column(TimestampTZ, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(TimestampTZ, default=utc_now, onupdate=utc_now)
    deleted_at: Mapped[datetime | None] = mapped_column(TimestampTZ)  # session-level erasure


class Run(Base):
    __tablename__ = "runs"

    id: Mapped[str] = _id_col()
    session_id: Mapped[str | None] = mapped_column(
        Uuid(as_uuid=False), ForeignKey("sessions.id"), index=True
    )
    user_id: Mapped[str | None] = mapped_column(Uuid(as_uuid=False), ForeignKey("users.id"))
    status: Mapped[RunStatus] = mapped_column(pg_enum(RunStatus), default=RunStatus.QUEUED)
    schema_version: Mapped[str | None] = mapped_column(String)
    intent: Mapped[dict[str, Any] | None] = mapped_column(JSONType)
    risk: Mapped[dict[str, Any] | None] = mapped_column(JSONType)
    plan: Mapped[dict[str, Any] | None] = mapped_column(JSONType)  # kind/macro_id/rationale/rev
    budget: Mapped[dict[str, Any] | None] = mapped_column(JSONType)
    final_report: Mapped[dict[str, Any] | None] = mapped_column(JSONType)
    normalized_inputs: Mapped[dict[str, Any] | None] = mapped_column(JSONType)
    error: Mapped[dict[str, Any] | None] = mapped_column(JSONType)  # fatal only
    created_at: Mapped[datetime] = mapped_column(TimestampTZ, default=utc_now, index=True)
    started_at: Mapped[datetime | None] = mapped_column(TimestampTZ)
    finished_at: Mapped[datetime | None] = mapped_column(TimestampTZ)


class Message(Base):
    __tablename__ = "messages"
    __append_only__ = True

    id: Mapped[str] = _id_col()
    run_id: Mapped[str] = _run_fk()
    role: Mapped[str] = mapped_column(String)
    content: Mapped[str] = mapped_column(Text)
    artifact_ids: Mapped[list[str]] = mapped_column(UuidArray, default=list)
    evidence_ids: Mapped[list[str]] = mapped_column(UuidArray, default=list)
    step_id: Mapped[str | None] = mapped_column(Uuid(as_uuid=False))
    created_at: Mapped[datetime] = mapped_column(TimestampTZ, default=utc_now, index=True)


class Subtask(Base):
    __tablename__ = "subtasks"

    id: Mapped[str] = _id_col()
    run_id: Mapped[str] = _run_fk()
    type: Mapped[SubtaskType] = mapped_column(pg_enum(SubtaskType))
    capability: Mapped[str | None] = mapped_column(String)
    inputs: Mapped[dict[str, Any]] = mapped_column(JSONType, default=dict)
    depends_on: Mapped[list[str]] = mapped_column(UuidArray, default=list)  # DAG edges
    status: Mapped[TaskStatus] = mapped_column(pg_enum(TaskStatus), default=TaskStatus.PENDING)
    result_ref: Mapped[str | None] = mapped_column(String)
    is_actionable: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(TimestampTZ, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(TimestampTZ, default=utc_now, onupdate=utc_now)


class Step(Base):
    """Primitive op / tool call — the provenance + timeline unit (`state_schema.md` §8)."""

    __tablename__ = "steps"
    __append_only__ = True

    id: Mapped[str] = _id_col()
    run_id: Mapped[str] = _run_fk()
    subtask_id: Mapped[str | None] = mapped_column(Uuid(as_uuid=False), index=True)
    name: Mapped[str] = mapped_column(String)
    weight: Mapped[str] = mapped_column(String, default="light")  # light | heavy
    tool: Mapped[str | None] = mapped_column(String)
    tool_version: Mapped[str | None] = mapped_column(String)
    params: Mapped[dict[str, Any]] = mapped_column(JSONType, default=dict)
    input_ref: Mapped[dict[str, Any]] = mapped_column(JSONType, default=dict)
    input_hash: Mapped[str | None] = mapped_column(String)  # cache key (PROV-5)
    output_ref: Mapped[str | None] = mapped_column(String)
    output_hash: Mapped[str | None] = mapped_column(String)
    job_id: Mapped[str | None] = mapped_column(String)  # async heavy steps
    status: Mapped[TaskStatus] = mapped_column(pg_enum(TaskStatus), default=TaskStatus.PENDING)
    nondeterministic: Mapped[bool] = mapped_column(Boolean, default=False)
    seed: Mapped[int | None] = mapped_column(Integer)
    cache_hit: Mapped[bool] = mapped_column(Boolean, default=False)
    started_at: Mapped[datetime | None] = mapped_column(TimestampTZ, index=True)
    finished_at: Mapped[datetime | None] = mapped_column(TimestampTZ)
    error: Mapped[str | None] = mapped_column(Text)


class EvidenceItem(Base):
    __tablename__ = "evidence_items"
    __append_only__ = True

    id: Mapped[str] = _id_col()
    run_id: Mapped[str] = _run_fk()
    subtask_id: Mapped[str | None] = mapped_column(Uuid(as_uuid=False))
    step_id: Mapped[str | None] = mapped_column(Uuid(as_uuid=False), index=True)
    source: Mapped[str | None] = mapped_column(String)
    source_kind: Mapped[SourceKind | None] = mapped_column(pg_enum(SourceKind))
    claim: Mapped[str | None] = mapped_column(Text)
    value: Mapped[dict[str, Any] | None] = mapped_column(JSONType)
    confidence: Mapped[dict[str, Any] | None] = mapped_column(JSONType)  # band/score/basis
    provenance: Mapped[dict[str, Any] | None] = mapped_column(JSONType)  # tool/version/…/hashes
    supersedes: Mapped[str | None] = mapped_column(
        Uuid(as_uuid=False), ForeignKey("evidence_items.id")
    )  # corrections reference the row they replace (PROV-3)
    created_at: Mapped[datetime] = mapped_column(TimestampTZ, default=utc_now)


class Artifact(Base):
    """Metadata only; heavy payload lives in the object store under ``storage_ref`` (RS-5)."""

    __tablename__ = "artifacts"
    __append_only__ = True

    id: Mapped[str] = _id_col()
    run_id: Mapped[str] = _run_fk()
    subtask_id: Mapped[str | None] = mapped_column(Uuid(as_uuid=False))
    type: Mapped[ArtifactType] = mapped_column(pg_enum(ArtifactType))
    title: Mapped[str | None] = mapped_column(String)
    storage_ref: Mapped[str | None] = mapped_column(String)  # object-store key
    storage_hash: Mapped[str | None] = mapped_column(String)
    summary: Mapped[dict[str, Any] | None] = mapped_column(JSONType)  # inline preview/metadata
    actionable: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(TimestampTZ, default=utc_now)

    evidence: Mapped[list[EvidenceItem]] = relationship(
        secondary="artifact_evidence", lazy="selectin"
    )


class ArtifactEvidence(Base):
    """Link table: artifact ↔ supporting evidence (`relational_schema.md` §4, PROV-2)."""

    __tablename__ = "artifact_evidence"

    artifact_id: Mapped[str] = mapped_column(
        Uuid(as_uuid=False), ForeignKey("artifacts.id"), primary_key=True
    )
    evidence_id: Mapped[str] = mapped_column(
        Uuid(as_uuid=False), ForeignKey("evidence_items.id"), primary_key=True
    )


class Clarification(Base):
    __tablename__ = "clarifications"

    id: Mapped[str] = _id_col()
    run_id: Mapped[str] = _run_fk()
    question: Mapped[str] = mapped_column(Text)
    options: Mapped[list[dict[str, Any]]] = mapped_column(JSONType, default=list)
    allow_multiple: Mapped[bool] = mapped_column(Boolean, default=False)
    allow_freeform: Mapped[bool] = mapped_column(Boolean, default=True)
    blocking: Mapped[bool] = mapped_column(Boolean, default=True)
    answer: Mapped[dict[str, Any] | None] = mapped_column(JSONType)
    created_at: Mapped[datetime] = mapped_column(TimestampTZ, default=utc_now)


class ReviewItem(Base):
    """Actionable-biology gate (`human_review_policy.md`)."""

    __tablename__ = "review_items"

    id: Mapped[str] = _id_col()
    run_id: Mapped[str] = _run_fk()
    subject_ref: Mapped[str] = mapped_column(String)  # artifact/subtask under review
    reason: Mapped[str | None] = mapped_column(Text)
    risks: Mapped[list[str]] = mapped_column(JSONType, default=list)
    evidence_ids: Mapped[list[str]] = mapped_column(UuidArray, default=list)
    decision: Mapped[ReviewDecision] = mapped_column(
        pg_enum(ReviewDecision), default=ReviewDecision.PENDING
    )
    note: Mapped[str | None] = mapped_column(Text)
    decided_by: Mapped[str | None] = mapped_column(Uuid(as_uuid=False), ForeignKey("users.id"))
    decided_at: Mapped[datetime | None] = mapped_column(TimestampTZ)
    created_at: Mapped[datetime] = mapped_column(TimestampTZ, default=utc_now)


class RunError(Base):
    __tablename__ = "run_errors"
    __append_only__ = True

    id: Mapped[str] = _id_col()
    run_id: Mapped[str] = _run_fk()
    subtask_id: Mapped[str | None] = mapped_column(Uuid(as_uuid=False))
    step_id: Mapped[str | None] = mapped_column(Uuid(as_uuid=False))
    kind: Mapped[str] = mapped_column(String)
    message: Mapped[str] = mapped_column(Text)
    recoverable: Mapped[bool] = mapped_column(Boolean, default=True)
    at: Mapped[datetime] = mapped_column(TimestampTZ, default=utc_now)


class Macro(Base):
    """Stored recipe referenced by ``runs.plan.macro_id`` (`routing_policy.md`); versioned."""

    __tablename__ = "macros"

    id: Mapped[str] = _id_col()
    key: Mapped[str] = mapped_column(String, unique=True)  # human-readable
    version: Mapped[str | None] = mapped_column(String)
    definition: Mapped[dict[str, Any]] = mapped_column(JSONType, default=dict)  # subtask template
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(TimestampTZ, default=utc_now)


class AuditLog(Base):
    """Immutable, hash-chained audit trail (audit_log.md §3, AL-2, AL-4).

    Every row is insert-only; no UPDATE or DELETE in normal operation. The ``hash`` column forms
    a tamper-evident chain: each entry's hash covers all its own fields plus ``prev_hash``, so
    any retroactive edit breaks every successor.
    """

    __tablename__ = "audit_log"
    __append_only__ = True

    __table_args__ = (
        Index("ix_audit_log_run_id_at", "run_id", "at"),
        Index("ix_audit_log_session_id_at", "session_id", "at"),
        Index("ix_audit_log_event_type_at", "event_type", "at"),
    )

    id: Mapped[str] = _id_col()
    event_type: Mapped[str] = mapped_column(String, nullable=False)
    actor: Mapped[dict[str, Any]] = mapped_column(JSONType, nullable=False)
    run_id: Mapped[str | None] = mapped_column(Uuid(as_uuid=False), nullable=True, index=False)
    session_id: Mapped[str | None] = mapped_column(Uuid(as_uuid=False), nullable=True, index=False)
    subject_ref: Mapped[str | None] = mapped_column(String, nullable=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONType, default=dict)
    at: Mapped[datetime] = mapped_column(TimestampTZ, default=utc_now, nullable=False)
    prev_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    hash: Mapped[str] = mapped_column(String(64), nullable=False)


# Tables whose rows are insert-only in normal operation (RS-2, PROV-3). The repository layer
# checks this set; corrections insert a new row with `supersedes`.
APPEND_ONLY_TABLES: frozenset[str] = frozenset(
    m.__tablename__ for m in Base.__subclasses__() if getattr(m, "__append_only__", False)
)

__all__ = [
    "Base", "User", "WorkspaceSession", "Run", "Message", "Subtask", "Step", "EvidenceItem",
    "Artifact", "ArtifactEvidence", "Clarification", "ReviewItem", "RunError", "Macro",
    "AuditLog", "APPEND_ONLY_TABLES",
]
