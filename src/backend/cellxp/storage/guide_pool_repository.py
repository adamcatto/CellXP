"""Durable CRUD for ordered, versioned CRISPR guide pools."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from cellxp.api.schemas import GuidePoolResponse, SaveGuidePoolRequest
from cellxp.domain.ids import new_id

from . import models as orm


class GuidePoolConflictError(RuntimeError):
    pass


class GuidePoolRepository:
    def __init__(self, factory: sessionmaker[Session]) -> None:
        self.factory = factory

    def save(
        self, source_artifact_id: str, request: SaveGuidePoolRequest, *, pool_id: str | None = None
    ) -> GuidePoolResponse:
        now = datetime.now(UTC)
        with self.factory.begin() as db:
            row = db.get(orm.GuidePool, pool_id) if pool_id else None
            if row is None:
                if request.expected_revision is not None:
                    raise GuidePoolConflictError("new guide pool cannot have expected_revision")
                row = orm.GuidePool(
                    id=new_id(), session_id=request.session_id,
                    source_artifact_id=source_artifact_id, name=request.name,
                    guide_ids=request.guide_ids, revision=0, created_at=now, updated_at=now,
                )
                db.add(row)
                db.flush()
            else:
                if row.source_artifact_id != source_artifact_id:
                    raise GuidePoolConflictError("guide pool belongs to another artifact")
                if request.expected_revision != row.revision:
                    raise GuidePoolConflictError("guide pool revision conflict")
                row.name = request.name
                row.guide_ids = request.guide_ids
                row.revision += 1
                row.updated_at = now
                db.flush()
            return _response(row)

    def list_for_artifact(self, source_artifact_id: str) -> list[GuidePoolResponse]:
        with self.factory() as db:
            rows = db.scalars(
                select(orm.GuidePool)
                .where(orm.GuidePool.source_artifact_id == source_artifact_id)
                .order_by(orm.GuidePool.created_at)
            )
            return [_response(row) for row in rows]

    def get(self, pool_id: str) -> GuidePoolResponse | None:
        with self.factory() as db:
            row = db.get(orm.GuidePool, pool_id)
            return _response(row) if row is not None else None


def _response(row: orm.GuidePool) -> GuidePoolResponse:
    return GuidePoolResponse(
        id=row.id, session_id=row.session_id, source_artifact_id=row.source_artifact_id,
        name=row.name, guide_ids=list(row.guide_ids), revision=row.revision,
        created_at=row.created_at.isoformat(), updated_at=row.updated_at.isoformat(),
    )
