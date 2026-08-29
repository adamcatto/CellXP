"""Audit log domain models and event-type constants (AL-1..6, specs/data/audit_log.md §2-3).

The audit log is the immutable, accountability-focused trail of consequential events: safety
refusals, review decisions, actionable outputs, side effects, and lifecycle events. It complements
the per-run provenance graph (which answers *how*); the audit log answers *who did/decided/was-
refused what, when*.
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

from cellxp.domain.ids import new_id


class AuditEventType:
    """Stable string constants for the event catalog (audit_log.md §2)."""

    REVIEW_REQUESTED = "review.requested"
    REVIEW_DECIDED = "review.decided"
    SAFETY_REFUSED = "safety.refused"
    SAFETY_RESTRICTED = "safety.restricted"
    ACTIONABLE_EMITTED = "actionable.emitted"
    SIDE_EFFECT_PERFORMED = "side_effect.performed"
    SESSION_CREATED = "session.created"
    SESSION_DELETED = "session.deleted"
    DATA_DELETED = "data.deleted"
    ACCESS_URL_ISSUED = "access.url_issued"
    CONFIG_CHANGED = "config.changed"


def _utc_now_iso() -> str:
    return datetime.now(UTC).isoformat()


class Actor(BaseModel):
    """Who or what caused the audited event (audit_log.md §3)."""

    kind: Literal["user", "agent", "system"]
    id: str | None = None


AGENT_ACTOR = Actor(kind="agent")
SYSTEM_ACTOR = Actor(kind="system")


def _compute_entry_hash(entry_data: dict[str, Any]) -> str:
    """SHA-256 over a canonical JSON of all fields except 'hash' itself (AL-4).

    `prev_hash` is included so the chain is tamper-evident: mutating any prior entry's
    data or deleting it breaks every successor hash.
    """
    hashable = {k: v for k, v in entry_data.items() if k != "hash"}
    canonical = json.dumps(hashable, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode()).hexdigest()


class AuditEntry(BaseModel):
    """A single append-only audit record (audit_log.md §3).

    `hash` is auto-computed on first construction if left blank; pass it explicitly only
    when loading an existing row from the database (so the stored hash is preserved for
    chain verification rather than recomputed from potentially different timestamps).
    """

    id: str = Field(default_factory=new_id)
    event_type: str
    actor: Actor
    run_id: str | None = None
    session_id: str | None = None
    subject_ref: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)
    at: str = Field(default_factory=_utc_now_iso)
    prev_hash: str | None = None
    hash: str = ""

    def model_post_init(self, __context: Any, /) -> None:
        if not self.hash:
            data = self.model_dump(mode="json")
            object.__setattr__(self, "hash", _compute_entry_hash(data))

    def verify(self) -> bool:
        """Re-derive hash and confirm it matches the stored value (AL-4)."""
        data = self.model_dump(mode="json")
        expected = _compute_entry_hash(data)
        return self.hash == expected


__all__ = [
    "AGENT_ACTOR",
    "SYSTEM_ACTOR",
    "Actor",
    "AuditEntry",
    "AuditEventType",
]
