"""Repositories — the AgentState ⇄ relational mapping and append-only enforcement.

This is the boundary the spec names as the writer of history (`relational_schema.md`,
`provenance_model.md`): services never persist, the repository does. It maps an in-run
`AgentState` to the `relational_schema.md` §4 tables and reconstructs an equivalent state by
`run_id` (RS-3), and it refuses in-place mutation/deletion of append-only tables — corrections
are new rows carrying `supersedes` (RS-2, PROV-3).

All CellXP timestamps are UTC by invariant (`clock.py`); on load a naive datetime (e.g. from a
tz-stripping SQLite test backend) is re-stamped UTC so the ISO round-trip is exact on Postgres
and SQLite alike.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from cellxp.agent.state import (
    AgentState,
    Budget,
    Clarification,
    NormalizedInputs,
    Plan,
    Report,
    ReviewItem,
    ReviewState,
    RunError,
    Subtask,
)
from cellxp.agent.state import (
    Message as StateMessage,
)
from cellxp.agent.state import (
    Step as StateStep,
)
from cellxp.domain.artifacts import ArtifactRef
from cellxp.domain.enums import IntentType, RunStatus
from cellxp.domain.errors import CellXPError
from cellxp.domain.evidence import Confidence, EvidenceItem, Provenance
from cellxp.domain.safety import RiskAssessment

from . import models as orm
from .models import APPEND_ONLY_TABLES


class AppendOnlyError(CellXPError):
    """Attempt to update/delete a row in an append-only table (RS-2, PROV-3)."""


# --- timestamp helpers -----------------------------------------------------------------------


def _parse_dt(value: str | None) -> datetime | None:
    return datetime.fromisoformat(value) if value else None


def _iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:  # tz-stripping backend (SQLite); CellXP times are UTC
        value = value.replace(tzinfo=UTC)
    return value.isoformat()


def _req_iso(value: datetime) -> str:
    """`_iso` for a non-nullable timestamp column — always returns a string."""
    return _iso(value) or datetime.now(UTC).isoformat()


def _dump(model: Any) -> dict[str, Any] | None:
    return model.model_dump(mode="json") if model is not None else None


# --- mutation guard --------------------------------------------------------------------------


def _ensure_mutable(obj: object) -> None:
    table = getattr(type(obj), "__tablename__", None)
    if table in APPEND_ONLY_TABLES:
        raise AppendOnlyError(
            f"{table!r} is append-only; insert a correcting row with `supersedes` "
            f"instead of mutating/deleting (PROV-3)"
        )


class StateRepository:
    """Persists and reloads an `AgentState` against the relational history."""

    def __init__(self, session: Session) -> None:
        self.session = session

    # -- write -------------------------------------------------------------------------------

    def save(
        self, state: AgentState, *, session_id: str | None = None, user_id: str | None = None
    ) -> str:
        """Persist `state` and return its `run_id`. Inserts a `runs` row plus its children."""
        run_id = state["run_id"]
        intent = state.get("intent")
        run = orm.Run(
            id=run_id,
            session_id=session_id,
            user_id=user_id,
            status=state.get("status", RunStatus.QUEUED),
            schema_version=state.get("schema_version"),
            intent=intent.value if isinstance(intent, IntentType) else intent,
            risk=_dump(state.get("risk")),
            plan=_dump(state.get("plan")),
            budget=_dump(state.get("budget")),
            final_report=_dump(state.get("final_report")),
            normalized_inputs=_dump(state.get("normalized_inputs")),
            created_at=_parse_dt(state.get("created_at")) or datetime.now(UTC),
        )
        self.session.merge(run)

        for m in state.get("messages", []):
            self.session.add(
                orm.Message(
                    id=m.id, run_id=run_id, role=m.role, content=m.content,
                    artifact_ids=list(m.artifact_ids), evidence_ids=list(m.evidence_ids),
                    step_id=m.step_id, created_at=_parse_dt(m.created_at),
                )
            )
        for st in state.get("subtasks", []):
            self.session.add(
                orm.Subtask(
                    id=st.id, run_id=run_id, type=st.type, capability=st.capability,
                    inputs=dict(st.inputs), depends_on=list(st.depends_on), status=st.status,
                    result_ref=st.result_ref, is_actionable=st.is_actionable,
                )
            )
        for sp in state.get("steps", []):
            self.session.add(
                orm.Step(
                    id=sp.id, run_id=run_id, subtask_id=sp.subtask_id, name=sp.name,
                    weight=sp.weight, tool=sp.tool, tool_version=sp.tool_version,
                    params=dict(sp.params), input_ref=dict(sp.input_ref),
                    output_ref=sp.output_ref, job_id=sp.job_id, status=sp.status,
                    started_at=_parse_dt(sp.started_at), finished_at=_parse_dt(sp.finished_at),
                    error=sp.error,
                )
            )
        for ev in state.get("evidence", []):
            self.session.add(
                orm.EvidenceItem(
                    id=ev.id, run_id=run_id, subtask_id=ev.subtask_id, step_id=ev.step_id,
                    source=ev.source, source_kind=ev.source_kind, claim=ev.claim, value=ev.value,
                    confidence=_dump(ev.confidence), provenance=_dump(ev.provenance),
                    supersedes=ev.provenance.supersedes,
                )
            )
        for art in state.get("artifacts", []):
            self.session.add(
                orm.Artifact(
                    id=art.id, run_id=run_id, subtask_id=art.subtask_id, type=art.type,
                    title=art.title, storage_ref=art.storage_ref, summary=dict(art.summary),
                    actionable=art.actionable, created_at=_parse_dt(art.created_at),
                )
            )
            for evid in art.evidence_ids:
                self.session.add(orm.ArtifactEvidence(artifact_id=art.id, evidence_id=evid))
        for cl in state.get("clarifications", []):
            self.session.add(
                orm.Clarification(
                    id=cl.id, run_id=run_id, question=cl.question,
                    options=[o.model_dump(mode="json") for o in cl.options],
                    allow_multiple=cl.allow_multiple, allow_freeform=cl.allow_freeform,
                    blocking=cl.blocking, answer=_dump(cl.answer),
                )
            )
        review = state.get("review")
        if review is not None:
            for ri in review.items:
                self.session.add(
                    orm.ReviewItem(
                        id=ri.id, run_id=run_id, subject_ref=ri.subject_ref, reason=ri.reason,
                        risks=list(ri.risks), evidence_ids=list(ri.evidence_ids),
                        decision=ri.decision, note=ri.note,
                    )
                )
        for er in state.get("errors", []):
            self.session.add(
                orm.RunError(
                    id=er.id, run_id=run_id, subtask_id=er.subtask_id, step_id=er.step_id,
                    kind=er.kind, message=er.message, recoverable=er.recoverable,
                    at=_parse_dt(er.at),
                )
            )
        self.session.flush()
        return run_id

    # -- read --------------------------------------------------------------------------------

    def load(self, run_id: str) -> AgentState:
        """Reconstruct an `AgentState` equivalent to what was saved (RS-3)."""
        run = self.session.get(orm.Run, run_id)
        if run is None:
            raise KeyError(f"no run {run_id!r}")

        state: AgentState = {"run_id": run.id, "status": run.status}
        if run.schema_version is not None:
            state["schema_version"] = run.schema_version
        if run.created_at is not None:
            state["created_at"] = _iso(run.created_at)  # type: ignore[typeddict-item]
        if run.intent is not None:
            state["intent"] = IntentType(run.intent)
        if run.risk is not None:
            state["risk"] = RiskAssessment.model_validate(run.risk)
        if run.plan is not None:
            state["plan"] = Plan.model_validate(run.plan)
        if run.budget is not None:
            state["budget"] = Budget.model_validate(run.budget)
        if run.final_report is not None:
            state["final_report"] = Report.model_validate(run.final_report)
        if run.normalized_inputs is not None:
            state["normalized_inputs"] = NormalizedInputs.model_validate(run.normalized_inputs)

        state["messages"] = [
            StateMessage(
                id=m.id, role=m.role, content=m.content, created_at=_req_iso(m.created_at),
                artifact_ids=list(m.artifact_ids), evidence_ids=list(m.evidence_ids),
                step_id=m.step_id,
            )
            for m in self._children(orm.Message, run_id, orm.Message.created_at)
        ]
        state["subtasks"] = [
            Subtask(
                id=s.id, type=s.type, capability=s.capability, inputs=dict(s.inputs),
                depends_on=list(s.depends_on), status=s.status, result_ref=s.result_ref,
                is_actionable=s.is_actionable,
            )
            for s in self._children(orm.Subtask, run_id)
        ]
        state["steps"] = [
            StateStep(
                id=s.id, subtask_id=s.subtask_id, name=s.name, weight=s.weight, tool=s.tool,
                tool_version=s.tool_version, params=dict(s.params), input_ref=dict(s.input_ref),
                output_ref=s.output_ref, job_id=s.job_id, status=s.status,
                started_at=_iso(s.started_at), finished_at=_iso(s.finished_at), error=s.error,
            )
            for s in self._children(orm.Step, run_id, orm.Step.started_at)
        ]
        state["evidence"] = [
            EvidenceItem(
                id=e.id, source=e.source, source_kind=e.source_kind, claim=e.claim, value=e.value,
                confidence=Confidence.model_validate(e.confidence),
                provenance=Provenance.model_validate(e.provenance or {}),
                subtask_id=e.subtask_id, step_id=e.step_id,
            )
            for e in self._children(orm.EvidenceItem, run_id)
        ]
        state["artifacts"] = [
            ArtifactRef(
                id=a.id, type=a.type, title=a.title, subtask_id=a.subtask_id,
                storage_ref=a.storage_ref, summary=dict(a.summary or {}),
                evidence_ids=self._artifact_evidence_ids(a.id), actionable=a.actionable,
                created_at=_req_iso(a.created_at),
            )
            for a in self._children(orm.Artifact, run_id, orm.Artifact.created_at)
        ]
        state["clarifications"] = [
            Clarification(
                id=c.id, question=c.question, options=c.options, allow_multiple=c.allow_multiple,
                allow_freeform=c.allow_freeform, blocking=c.blocking, answer=c.answer,
            )
            for c in self._children(orm.Clarification, run_id)
        ]
        review_items = [
            ReviewItem(
                id=r.id, subject_ref=r.subject_ref, reason=r.reason, risks=list(r.risks),
                evidence_ids=list(r.evidence_ids), decision=r.decision, note=r.note,
            )
            for r in self._children(orm.ReviewItem, run_id)
        ]
        if review_items:
            state["review"] = ReviewState(required=True, items=review_items)
        state["errors"] = [
            RunError(
                id=e.id, subtask_id=e.subtask_id, step_id=e.step_id, kind=e.kind,
                message=e.message, recoverable=e.recoverable, at=_req_iso(e.at),
            )
            for e in self._children(orm.RunError, run_id, orm.RunError.at)
        ]
        return state

    # -- guarded mutation --------------------------------------------------------------------

    def delete(self, obj: object) -> None:
        """Delete a row — refused for append-only tables (RS-2)."""
        _ensure_mutable(obj)
        self.session.delete(obj)

    def update(self, obj: object, **changes: Any) -> None:
        """Update a row in place — refused for append-only tables (RS-2)."""
        _ensure_mutable(obj)
        for key, val in changes.items():
            setattr(obj, key, val)

    # -- helpers -----------------------------------------------------------------------------

    def _children(self, model: type, run_id: str, order_by: Any = None) -> list[Any]:
        stmt: Any = select(model).where(model.run_id == run_id)  # type: ignore[attr-defined]
        if order_by is not None:
            stmt = stmt.order_by(order_by)
        return list(self.session.scalars(stmt))

    def _artifact_evidence_ids(self, artifact_id: str) -> list[str]:
        stmt = (
            select(orm.ArtifactEvidence.evidence_id)
            .where(orm.ArtifactEvidence.artifact_id == artifact_id)
            .order_by(orm.ArtifactEvidence.evidence_id)
        )
        return list(self.session.scalars(stmt))
