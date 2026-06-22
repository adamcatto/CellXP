"""Durable repository for the HTTP session/run/SSE contract."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from cellxp.api.schemas import CreateRunRequest, RunEvent, SessionDefaults, SessionSummary
from cellxp.domain.enums import RunStatus

from . import models as orm


def _iso(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.isoformat()


class ApiRepository:
    """Small transactional repository used by the API runtime across replicas/restarts."""

    def __init__(self, factory: sessionmaker[Session]) -> None:
        self.factory = factory

    def create_session(self, summary: SessionSummary) -> None:
        with self.factory.begin() as db:
            db.add(orm.WorkspaceSession(
                id=summary.id, type=summary.type, title=summary.title,
                defaults={**summary.defaults.model_dump(mode="json"), "_revision": summary.revision},
                created_at=datetime.fromisoformat(summary.created_at),
                updated_at=datetime.fromisoformat(summary.updated_at),
            ))

    def sessions(self) -> list[SessionSummary]:
        with self.factory() as db:
            rows = list(db.scalars(select(orm.WorkspaceSession).where(
                orm.WorkspaceSession.deleted_at.is_(None)
            ).order_by(orm.WorkspaceSession.created_at)))
            return [self._session(db, row) for row in rows]

    def get_session(self, session_id: str) -> SessionSummary | None:
        with self.factory() as db:
            row = db.get(orm.WorkspaceSession, session_id)
            if row is None or row.deleted_at is not None:
                return None
            return self._session(db, row)

    def update_session(self, summary: SessionSummary) -> None:
        with self.factory.begin() as db:
            row = db.get(orm.WorkspaceSession, summary.id)
            if row is None:
                raise KeyError(summary.id)
            row.title = summary.title
            row.defaults = {
                **summary.defaults.model_dump(mode="json"), "_revision": summary.revision
            }
            row.updated_at = datetime.fromisoformat(summary.updated_at)

    def delete_session(self, session_id: str) -> bool:
        with self.factory.begin() as db:
            row = db.get(orm.WorkspaceSession, session_id)
            if row is None or row.deleted_at is not None:
                return False
            row.deleted_at = datetime.now(timezone.utc)
            return True

    def save_run(self, snapshot: dict[str, Any], request: CreateRunRequest) -> None:
        status = RunStatus(snapshot["status"])
        with self.factory.begin() as db:
            run = db.get(orm.Run, snapshot["id"])
            if run is None:
                run = orm.Run(
                    id=snapshot["id"], session_id=snapshot["session_id"], status=status,
                    created_at=datetime.fromisoformat(snapshot["created_at"]),
                )
                db.add(run)
            else:
                run.status = status
            state = db.get(orm.ApiRunState, snapshot["id"])
            values = request.model_dump(mode="json")
            if state is None:
                db.add(orm.ApiRunState(
                    run_id=snapshot["id"], client_request_id=request.client_request_id,
                    request=values, snapshot=snapshot,
                ))
            else:
                state.snapshot = snapshot
                state.request = values

    def find_run(self, session_id: str, client_request_id: str) -> str | None:
        with self.factory() as db:
            return db.scalar(select(orm.ApiRunState.run_id).join(orm.Run).where(
                orm.Run.session_id == session_id,
                orm.ApiRunState.client_request_id == client_request_id,
            ))

    def runs(self, session_id: str | None = None) -> list[tuple[dict[str, Any], CreateRunRequest]]:
        with self.factory() as db:
            stmt = select(orm.ApiRunState).join(orm.Run).order_by(orm.Run.created_at)
            if session_id is not None:
                stmt = stmt.where(orm.Run.session_id == session_id)
            return [
                (dict(row.snapshot), CreateRunRequest.model_validate(row.request))
                for row in db.scalars(stmt)
            ]

    def append_event(self, run_id: str, kind: str, event: RunEvent) -> None:
        with self.factory.begin() as db:
            db.add(orm.ApiRunEvent(
                run_id=run_id, sequence=event.seq, kind=kind,
                payload=event.model_dump(mode="json"), at=datetime.fromisoformat(event.at),
            ))

    def events_after(self, run_id: str, sequence: int) -> list[tuple[str, RunEvent]]:
        with self.factory() as db:
            rows = db.scalars(select(orm.ApiRunEvent).where(
                orm.ApiRunEvent.run_id == run_id, orm.ApiRunEvent.sequence > sequence,
            ).order_by(orm.ApiRunEvent.sequence))
            return [(row.kind, RunEvent.model_validate(row.payload)) for row in rows]

    @staticmethod
    def _session(db: Session, row: orm.WorkspaceSession) -> SessionSummary:
        defaults = dict(row.defaults or {})
        revision = int(defaults.pop("_revision", 0))
        run_count = db.scalar(select(func.count()).select_from(orm.Run).where(
            orm.Run.session_id == row.id
        )) or 0
        artifact_count = db.scalar(select(func.count()).select_from(orm.Artifact).join(orm.Run).where(
            orm.Run.session_id == row.id
        )) or 0
        return SessionSummary(
            id=row.id, type=row.type or "general", title=row.title or "Untitled",
            defaults=SessionDefaults.model_validate(defaults), revision=revision,
            created_at=_iso(row.created_at), updated_at=_iso(row.updated_at),
            run_count=run_count, artifact_count=artifact_count,
        )
