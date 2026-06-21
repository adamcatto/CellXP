"""Insert-only audit log repository with SHA-256 hash chain (AL-1..6, audit_log.md §3-5).

The repository enforces append-only semantics at the application layer (AL-2): only
`append()` is provided; no update or delete path exists. The hash chain is threaded by
linking each new entry to the `hash` of the most recent entry in the same `run_id` or
`session_id` partition (AL-4). `verify_chain()` walks the chain and re-derives each hash.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from cellxp.domain.audit import AuditEntry, Actor
from cellxp.storage.models import AuditLog


def _to_orm(entry: AuditEntry) -> AuditLog:
    at = datetime.fromisoformat(entry.at) if isinstance(entry.at, str) else entry.at
    if at.tzinfo is None:
        at = at.replace(tzinfo=timezone.utc)
    return AuditLog(
        id=entry.id,
        event_type=entry.event_type,
        actor=entry.actor.model_dump(mode="json"),
        run_id=entry.run_id,
        session_id=entry.session_id,
        subject_ref=entry.subject_ref,
        payload=entry.payload,
        at=at,
        prev_hash=entry.prev_hash,
        hash=entry.hash,
    )


def _from_orm(row: AuditLog) -> AuditEntry:
    at = row.at
    if isinstance(at, datetime):
        # SQLite drops timezone info; restore UTC so the ISO string matches the original
        # form used when the hash was computed (+00:00 suffix).
        if at.tzinfo is None:
            at = at.replace(tzinfo=timezone.utc)
        at_str = at.isoformat()
    else:
        at_str = str(at)
    return AuditEntry.model_validate(
        {
            "id": row.id,
            "event_type": row.event_type,
            "actor": row.actor,
            "run_id": row.run_id,
            "session_id": row.session_id,
            "subject_ref": row.subject_ref,
            "payload": row.payload or {},
            "at": at_str,
            "prev_hash": row.prev_hash,
            "hash": row.hash,
        }
    )


class AuditRepository:
    """Write-side audit log accessor.  All mutations are inserts (AL-2).

    The caller must supply an open `Session`; transaction management (commit/rollback) is the
    caller's responsibility so that audit writes can participate in the same transaction as the
    state update that triggered them.
    """

    def __init__(self, session: Session) -> None:
        self._session = session

    # ------------------------------------------------------------------
    # Chain helpers
    # ------------------------------------------------------------------

    def _latest_hash(self, *, run_id: str | None, session_id: str | None) -> str | None:
        """Hash of the most recent entry in this run/session partition, or None."""
        q = self._session.query(AuditLog)
        if run_id:
            q = q.filter(AuditLog.run_id == run_id)
        elif session_id:
            q = q.filter(AuditLog.session_id == session_id)
        else:
            # Global chain tail — used when neither run_id nor session_id is set.
            q = q.filter(AuditLog.run_id.is_(None), AuditLog.session_id.is_(None))
        row = q.order_by(AuditLog.at.desc()).first()
        return row.hash if row else None

    # ------------------------------------------------------------------
    # Write path (the only mutation path — AL-2)
    # ------------------------------------------------------------------

    def append(
        self,
        *,
        event_type: str,
        actor: Actor,
        run_id: str | None = None,
        session_id: str | None = None,
        subject_ref: str | None = None,
        payload: dict[str, Any] | None = None,
    ) -> AuditEntry:
        """Insert a new audit entry linked to the chain tail and return it.

        The `prev_hash` is resolved from the most recent entry in the same partition
        (run_id takes precedence over session_id for chain scoping). The entry hash
        is computed by `AuditEntry.model_post_init` before insert.
        """
        prev_hash = self._latest_hash(run_id=run_id, session_id=session_id)
        entry = AuditEntry(
            event_type=event_type,
            actor=actor,
            run_id=run_id,
            session_id=session_id,
            subject_ref=subject_ref,
            payload=payload or {},
            prev_hash=prev_hash,
        )
        self._session.add(_to_orm(entry))
        return entry

    # ------------------------------------------------------------------
    # Read path (chain verification — AL-4)
    # ------------------------------------------------------------------

    def query(
        self,
        *,
        run_id: str | None = None,
        session_id: str | None = None,
        event_type: str | None = None,
    ) -> list[AuditEntry]:
        """Return entries ordered ascending by `at` (chain order)."""
        q = self._session.query(AuditLog)
        if run_id:
            q = q.filter(AuditLog.run_id == run_id)
        if session_id:
            q = q.filter(AuditLog.session_id == session_id)
        if event_type:
            q = q.filter(AuditLog.event_type == event_type)
        rows = q.order_by(AuditLog.at.asc()).all()
        return [_from_orm(r) for r in rows]

    def verify_chain(self, *, run_id: str | None = None, session_id: str | None = None) -> bool:
        """Walk entries in chain order and verify each hash links correctly (AL-4).

        Returns `True` if every entry's hash matches its recomputed value and its
        `prev_hash` equals the previous entry's `hash`. Returns `False` on first
        violation, indicating potential tampering.
        """
        entries = self.query(run_id=run_id, session_id=session_id)
        prev: AuditEntry | None = None
        for entry in entries:
            if not entry.verify():
                return False
            expected_prev = prev.hash if prev else None
            if entry.prev_hash != expected_prev:
                return False
            prev = entry
        return True


__all__ = ["AuditRepository"]
