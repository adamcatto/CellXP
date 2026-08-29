"""Process-local v1 runtime used by the single-user development deployment.

The durable repository will replace this adapter in regime 2. Keeping lifecycle logic behind this
small interface lets HTTP contract tests run without Postgres, Redis, Ollama, or model downloads.
"""

from __future__ import annotations

import json
from copy import deepcopy
from dataclasses import dataclass, field
from threading import RLock
from typing import Any

from fastapi import HTTPException
from langgraph.types import Command

from cellxp.agent.checkpoint import checkpointer_from_database_url
from cellxp.agent.graph import build_graph, production_capability_nodes
from cellxp.agent.state import Clarification, Report, ReviewState
from cellxp.api.schemas import (
    CreateRunRequest,
    CreateRunResponse,
    CreateSessionRequest,
    PatchSessionRequest,
    RunEvent,
    SessionDefaults,
    SessionSummary,
)
from cellxp.domain.clock import utc_now_iso
from cellxp.domain.enums import RunStatus
from cellxp.domain.ids import new_id


@dataclass
class RunRecord:
    snapshot: dict[str, Any]
    request: CreateRunRequest
    events: list[tuple[str, RunEvent]] = field(default_factory=list)
    graph: Any | None = None


class LocalRuntime:
    """Thread-safe, owner-local runtime with explicit idempotency and ordered events."""

    def __init__(self) -> None:
        self._lock = RLock()
        self.sessions: dict[str, SessionSummary] = {}
        self.runs: dict[str, RunRecord] = {}
        self._dedupe: dict[tuple[str, str], str] = {}

    def reset(self) -> None:
        with self._lock:
            self.sessions.clear()
            self.runs.clear()
            self._dedupe.clear()

    def create_session(self, request: CreateSessionRequest) -> SessionSummary:
        now = utc_now_iso()
        session = SessionSummary(
            id=new_id(), type=request.type, title=request.title, defaults=request.defaults,
            revision=0, created_at=now, updated_at=now,
        )
        with self._lock:
            self.sessions[session.id] = session
        return session.model_copy(deep=True)

    def list_sessions(self) -> list[SessionSummary]:
        with self._lock:
            return [item.model_copy(deep=True) for item in self.sessions.values()]

    def get_session(self, session_id: str) -> SessionSummary:
        with self._lock:
            session = self.sessions.get(session_id)
            if session is None:
                raise HTTPException(status_code=404, detail="session not found")
            return session.model_copy(deep=True)

    def patch_session(self, session_id: str, request: PatchSessionRequest) -> SessionSummary:
        with self._lock:
            session = self.sessions.get(session_id)
            if session is None:
                raise HTTPException(status_code=404, detail="session not found")
            if session.revision != request.expected_revision:
                raise HTTPException(status_code=409, detail="session revision conflict")
            if request.title is not None:
                session.title = request.title
            if request.defaults is not None:
                merged = session.defaults.model_dump(exclude_none=True)
                merged.update(request.defaults)
                session.defaults = SessionDefaults.model_validate(merged)
            session.revision += 1
            session.updated_at = utc_now_iso()
            return session.model_copy(deep=True)

    def delete_session(self, session_id: str) -> None:
        with self._lock:
            if session_id not in self.sessions:
                raise HTTPException(status_code=404, detail="session not found")
            del self.sessions[session_id]
            for run_id in [
                key for key, value in self.runs.items()
                if value.snapshot["session_id"] == session_id
            ]:
                del self.runs[run_id]

    def create_run(
        self,
        session_id: str,
        request: CreateRunRequest,
        *,
        reproduces_run_id: str | None = None,
    ) -> CreateRunResponse:
        session = self.get_session(session_id)
        key = (session_id, request.client_request_id)
        with self._lock:
            if existing := self._dedupe.get(key):
                return self._response(self.runs[existing].snapshot)

        run_id = new_id()
        now = utc_now_iso()
        snapshot: dict[str, Any] = {
            "id": run_id,
            "session_id": session_id,
            "status": RunStatus.QUEUED.value,
            "message": request.message,
            "steps": [], "evidence": [], "artifacts": [], "errors": [],
            "overrides": deepcopy(request.overrides),
            "provider": "ollama", "model": request.overrides.get("model", "gemma4:4b"),
            "created_at": now, "updated_at": now,
        }
        if reproduces_run_id:
            snapshot["reproduces_run_id"] = reproduces_run_id
        record = RunRecord(snapshot=snapshot, request=request)
        with self._lock:
            self.runs[run_id] = record
            self._dedupe[key] = run_id
            stored = self.sessions[session_id]
            stored.run_count += 1
            stored.updated_at = now
        self._emit(record, "run.status", {"status": "queued"})
        self._on_run_created(record)
        self._dispatch_start(record, session)
        return self._response(record.snapshot)

    def _dispatch_start(self, record: RunRecord, session: SessionSummary) -> None:
        self._execute(record, session)

    def _execute(self, record: RunRecord, session: SessionSummary) -> None:
        snapshot = record.snapshot
        snapshot["status"] = RunStatus.RUNNING.value
        self._emit(record, "run.status", {"status": "running"})
        graph = build_graph(
            checkpointer=self._checkpointer(), capability_nodes=production_capability_nodes()
        )
        record.graph = graph
        query = record.request.message or "Analyze the supplied inputs."
        if record.request.inputs:
            query = f"{query}\nInputs: " + json.dumps(
                [item.model_dump(mode="json") for item in record.request.inputs]
            )
        defaults = session.defaults.model_dump(exclude_none=True)
        context_parts = [defaults.get("organism"), defaults.get("assembly")]
        if any(context_parts):
            query = f"{query}\nSession context: {' '.join(item for item in context_parts if item)}"
        state: dict[str, Any] = {
            "run_id": snapshot["id"],
            "session_type": session.type,
            "review_posture": defaults.get("review_posture", "standard"),
            "user_query": query,
        }
        organism = record.request.overrides.get("organism") or defaults.get("organism")
        assembly = record.request.overrides.get("assembly") or defaults.get("assembly")
        if organism or assembly:
            state["normalized_inputs"] = {"organism": organism, "assembly": assembly}
        try:
            output = graph.invoke(
                state, {"configurable": {"thread_id": snapshot["id"]}}
            )
            self._apply_graph_output(record, output)
        except Exception as exc:  # noqa: BLE001  # boundary converts internal failures to safe stable output
            snapshot["status"] = RunStatus.FAILED.value
            snapshot["errors"] = [{
                "code": "run_failed", "message": "Run execution failed.", "fatal": True,
                "at": utc_now_iso(),
            }]
            self._emit(record, "error.added", snapshot["errors"][0])
            self._emit(record, "run.status", {"status": "failed"})
            # Preserve the exception only for local debugging without exposing it over HTTP.
            snapshot["_internal_error"] = type(exc).__name__

    def _apply_graph_output(self, record: RunRecord, output: dict[str, Any]) -> None:
        snapshot = record.snapshot
        snapshot["steps"] = [self._step(snapshot["id"], item) for item in output.get("steps", [])]
        snapshot["evidence"] = [
            self._evidence(snapshot["id"], item) for item in output.get("evidence", [])
        ]
        snapshot["artifacts"] = [
            self._artifact(snapshot["id"], item) for item in output.get("artifacts", [])
        ]
        snapshot["errors"] = [self._run_error(item) for item in output.get("errors", [])]
        if plan := output.get("plan"):
            snapshot["plan"] = self._json(plan)
        status = str(getattr(output.get("status"), "value", output.get("status", "running")))
        if output.get("__interrupt__"):
            if status == RunStatus.AWAITING_REVIEW.value:
                review = ReviewState.model_validate(output.get("review", {}))
                pending = next(item for item in review.items if item.decision.value == "pending")
                raw_pending = self._json(pending)
                artifact = next(
                    (
                        item for item in snapshot["artifacts"]
                        if item["id"] == raw_pending["subject_ref"]
                    ),
                    {
                        "id": raw_pending["subject_ref"], "run_id": snapshot["id"],
                        "type": "file", "title": "Actionable output", "status": "ready",
                        "actionable": True, "review_status": "pending",
                        "created_at": utc_now_iso(),
                    },
                )
                snapshot["pending_review"] = {
                    "id": raw_pending["id"], "run_id": snapshot["id"],
                    "artifact_ref": artifact, "rationale": raw_pending["reason"],
                    "risks": raw_pending["risks"],
                }
                self._on_review_requested(record, snapshot["pending_review"])
                self._emit(record, "review.requested", snapshot["pending_review"])
            else:
                clarification = next(
                    Clarification.model_validate(item)
                    for item in output.get("clarifications", [])
                    if Clarification.model_validate(item).answer is None
                )
                snapshot["pending_clarification"] = self._json(clarification)
                snapshot["pending_clarification"]["run_id"] = snapshot["id"]
                status = RunStatus.AWAITING_INPUT.value
                self._emit(record, "clarification.requested", snapshot["pending_clarification"])
        if report := output.get("final_report"):
            parsed = Report.model_validate(report)
            snapshot["report"] = parsed.markdown
            self._emit(record, "report.delta", {"token": parsed.markdown})
        if raw_review := output.get("review"):
            review = ReviewState.model_validate(raw_review)
            snapshot["review"] = self._json(review)
            decisions = {item.subject_ref: item.decision.value for item in review.items}
            for artifact in snapshot["artifacts"]:
                if artifact.get("actionable") and artifact["id"] in decisions:
                    artifact["review_status"] = decisions[artifact["id"]]
        snapshot["status"] = status
        snapshot["updated_at"] = utc_now_iso()
        self._emit(record, "run.status", {"status": status})
        if status == RunStatus.COMPLETED.value:
            self._emit(record, "run.completed", {
                "model": snapshot["model"], "provider": snapshot["provider"]
            })

    def resume(self, run_id: str, item_id: str, value: Any, expected_status: str) -> None:
        record = self._record(run_id)
        if record.snapshot["status"] != expected_status:
            raise HTTPException(status_code=409, detail="run is not awaiting this interaction")
        pending_key = "pending_review" if expected_status == "awaiting_review" else "pending_clarification"
        pending = record.snapshot.get(pending_key)
        if not pending or pending.get("id") != item_id:
            raise HTTPException(status_code=409, detail="interaction is no longer pending")
        self._dispatch_resume(record, item_id, value)

    def _dispatch_resume(self, record: RunRecord, item_id: str, value: Any) -> None:
        graph = record.graph
        if graph is None:
            graph = build_graph(
                checkpointer=self._checkpointer(), capability_nodes=production_capability_nodes()
            )
            record.graph = graph
        output = graph.invoke(
            Command(resume=value),
            {"configurable": {"thread_id": record.snapshot["id"]}},
        )
        record.snapshot.pop("pending_review", None)
        record.snapshot.pop("pending_clarification", None)
        self._apply_graph_output(record, output)

    def get_run(self, run_id: str) -> dict[str, Any]:
        snapshot = deepcopy(self._record(run_id).snapshot)
        snapshot.pop("_internal_error", None)
        snapshot.pop("_queued_resume", None)
        return snapshot

    def list_runs(self, session_id: str) -> list[dict[str, Any]]:
        self.get_session(session_id)
        with self._lock:
            return [
                self.get_run(run_id) for run_id, record in self.runs.items()
                if record.snapshot["session_id"] == session_id
            ]

    def cancel(self, run_id: str) -> None:
        record = self._record(run_id)
        if record.snapshot["status"] not in {"completed", "failed", "cancelled"}:
            record.snapshot["status"] = "cancelled"
            record.snapshot["updated_at"] = utc_now_iso()
            self._emit(record, "run.status", {"status": "cancelled"})

    def events_after(self, run_id: str, sequence: int) -> list[tuple[str, RunEvent]]:
        record = self._record(run_id)
        return [(kind, event) for kind, event in record.events if event.seq > sequence]

    def _record(self, run_id: str) -> RunRecord:
        with self._lock:
            record = self.runs.get(run_id)
            if record is None:
                raise HTTPException(status_code=404, detail="run not found")
            return record

    def _emit(self, record: RunRecord, kind: str, data: dict[str, Any]) -> None:
        event = RunEvent(
            run_id=record.snapshot["id"], seq=len(record.events) + 1,
            at=utc_now_iso(), data=deepcopy(data),
        )
        record.events.append((kind, event))

    def _checkpointer(self) -> Any:
        return checkpointer_from_database_url(None)

    def _on_run_created(self, record: RunRecord) -> None:
        """Persistence hook invoked before graph execution starts."""

    def _on_review_requested(self, record: RunRecord, pending: dict[str, Any]) -> None:
        """Durable runtimes persist review audit linkage; local tests keep no audit store."""

    def find_artifact(self, artifact_id: str) -> tuple[dict[str, Any], dict[str, Any]]:
        with self._lock:
            run_ids = list(self.runs)
        for run_id in run_ids:
            snapshot = self.get_run(run_id)
            for artifact in snapshot.get("artifacts", []):
                if artifact.get("id") == artifact_id:
                    return snapshot, artifact
        raise HTTPException(status_code=404, detail="artifact not found")

    def audit_entries(self, run_id: str) -> tuple[list[dict[str, Any]], bool]:
        self.get_run(run_id)
        return [], False

    def audit_export(self, run_id: str, artifact_id: str, payload: dict[str, Any]) -> None:
        del run_id, artifact_id, payload

    def record_export(self, artifact_id: str, descriptor: dict[str, Any]) -> None:
        snapshot, artifact = self.find_artifact(artifact_id)
        artifact.setdefault("exports", []).append(deepcopy(descriptor))
        record = self._record(snapshot["id"])
        record.snapshot = snapshot

    @staticmethod
    def _response(snapshot: dict[str, Any]) -> CreateRunResponse:
        run_id = snapshot["id"]
        return CreateRunResponse(
            run_id=run_id, session_id=snapshot["session_id"], status=snapshot["status"],
            stream_url=f"/api/v1/runs/{run_id}/events", created_at=snapshot["created_at"],
        )

    @staticmethod
    def _json(value: Any) -> dict[str, Any]:
        if hasattr(value, "model_dump"):
            return value.model_dump(mode="json")
        return deepcopy(value)

    @classmethod
    def _run_error(cls, value: Any) -> dict[str, Any]:
        raw = cls._json(value)
        return {
            "code": raw.get("kind", "run_error"), "message": raw.get("message", "Run error"),
            "fatal": not raw.get("recoverable", True), "step_id": raw.get("step_id"),
            "at": raw.get("at"),
        }

    @classmethod
    def _step(cls, run_id: str, value: Any) -> dict[str, Any]:
        raw = cls._json(value)
        raw_status = str(raw.get("status", "queued"))
        status = {"pending": "queued", "done": "completed"}.get(
            raw_status, raw_status
        )
        return {
            "id": raw["id"], "run_id": run_id, "subtask_id": raw.get("subtask_id"),
            "tool": raw.get("tool") or raw["name"], "label": raw["name"], "status": status,
            "tool_version": raw.get("tool_version"), "input_summary": None,
            "output_summary": raw.get("output_ref"), "evidence_ids": [], "artifact_ids": [],
            "started_at": raw.get("started_at"), "finished_at": raw.get("finished_at"),
            "error": raw.get("error"),
        }

    @classmethod
    def _evidence(cls, run_id: str, value: Any) -> dict[str, Any]:
        raw = cls._json(value)
        source_kind = str(raw.get("source_kind", "database"))
        kinds = {
            "model": "model_output", "database": "db_record",
            "literature": "citation", "measurement": "db_record", "computation": "db_record",
        }
        confidence = raw.get("confidence", {})
        return {
            "id": raw["id"], "run_id": run_id,
            "kind": kinds.get(source_kind, "db_record"),
            "source": raw["source"], "summary": raw.get("claim"),
            "confidence": {
                "value": confidence.get("score"), "band": confidence.get("band"),
                "notes": [confidence["basis"]] if confidence.get("basis") else [],
            },
            "retrieved_at": raw.get("provenance", {}).get("timestamp"),
            "step_id": raw.get("step_id"),
        }

    @classmethod
    def _artifact(cls, run_id: str, value: Any) -> dict[str, Any]:
        raw = cls._json(value)
        return {
            **raw, "run_id": run_id, "status": "ready",
            "review_status": "pending" if raw.get("actionable") else "not_required",
        }


class DurableRuntime(LocalRuntime):
    """Repository-backed runtime; only active graph execution remains replica-local."""

    def __init__(self, database_url: str) -> None:
        from cellxp.storage.api_repository import ApiRepository
        from cellxp.storage.database import Base, make_session_factory

        super().__init__()
        self.database_url = database_url
        self._durable_checkpointer: Any | None = None
        self._factory = make_session_factory(database_url)
        Base.metadata.create_all(bind=self._factory.kw["bind"])
        self.repository = ApiRepository(self._factory)
        self._hydrate()

    def _hydrate(self) -> None:
        self.sessions = {item.id: item for item in self.repository.sessions()}
        for snapshot, request in self.repository.runs():
            events = self.repository.events_after(snapshot["id"], 0)
            self.runs[snapshot["id"]] = RunRecord(
                snapshot=snapshot, request=request, events=events
            )
            self._dedupe[(snapshot["session_id"], request.client_request_id)] = snapshot["id"]

    def refresh_run(self, run_id: str) -> RunRecord:
        stored = self.repository.run(run_id)
        if stored is None:
            raise HTTPException(status_code=404, detail="run not found")
        snapshot, request = stored
        record = RunRecord(
            snapshot=snapshot, request=request,
            events=self.repository.events_after(run_id, 0),
        )
        with self._lock:
            self.runs[run_id] = record
        return record

    def create_session(self, request: CreateSessionRequest) -> SessionSummary:
        result = super().create_session(request)
        self.repository.create_session(result)
        return result

    def patch_session(self, session_id: str, request: PatchSessionRequest) -> SessionSummary:
        result = super().patch_session(session_id, request)
        self.repository.update_session(result)
        return result

    def delete_session(self, session_id: str) -> None:
        if not self.repository.delete_session(session_id):
            raise HTTPException(status_code=404, detail="session not found")
        with self._lock:
            self.sessions.pop(session_id, None)

    def create_run(
        self,
        session_id: str,
        request: CreateRunRequest,
        *,
        reproduces_run_id: str | None = None,
    ) -> CreateRunResponse:
        existing = self.repository.find_run(session_id, request.client_request_id)
        if existing is not None:
            return self._response(self._record(existing).snapshot)
        response = super().create_run(
            session_id, request, reproduces_run_id=reproduces_run_id
        )
        record = self._record(response.run_id)
        self.repository.save_run(record.snapshot, record.request)
        for kind, event in record.events[1:]:
            self.repository.append_event(response.run_id, kind, event)
        return response

    def _on_run_created(self, record: RunRecord) -> None:
        # Establish durable run identity before invoking any graph node. A process crash can then
        # be recovered from the graph checkpoint without losing the API-visible run.
        self.repository.save_run(record.snapshot, record.request)
        kind, event = record.events[-1]
        self.repository.append_event(record.snapshot["id"], kind, event)

    def _on_review_requested(self, record: RunRecord, pending: dict[str, Any]) -> None:
        from cellxp.domain.audit import AGENT_ACTOR, AuditEventType
        from cellxp.storage.audit_repository import AuditRepository

        with self._factory.begin() as db:
            repo = AuditRepository(db)
            existing = repo.query(run_id=record.snapshot["id"], event_type=AuditEventType.REVIEW_REQUESTED)
            if not any(item.subject_ref == pending["artifact_ref"]["id"] for item in existing):
                repo.append(
                    event_type=AuditEventType.REVIEW_REQUESTED, actor=AGENT_ACTOR,
                    run_id=record.snapshot["id"], session_id=record.snapshot["session_id"],
                    subject_ref=pending["artifact_ref"]["id"],
                    payload={"review_item_id": pending["id"]},
                )

    def _audit_review_decision(
        self, record: RunRecord, subject_ref: str, review_id: str, approved: bool
    ) -> None:
        from cellxp.domain.audit import AGENT_ACTOR, AuditEventType
        from cellxp.storage.audit_repository import AuditRepository

        with self._factory.begin() as db:
            repo = AuditRepository(db)
            repo.append(
                event_type=AuditEventType.REVIEW_DECIDED, actor=AGENT_ACTOR,
                run_id=record.snapshot["id"], session_id=record.snapshot["session_id"],
                subject_ref=subject_ref,
                payload={"review_item_id": review_id, "decision": "approved" if approved else "rejected"},
            )
            if approved:
                repo.append(
                    event_type=AuditEventType.ACTIONABLE_EMITTED, actor=AGENT_ACTOR,
                    run_id=record.snapshot["id"], session_id=record.snapshot["session_id"],
                    subject_ref=subject_ref,
                    payload={"artifact_id": subject_ref, "approving_review_item_id": review_id},
                )

    def resume(self, run_id: str, item_id: str, value: Any, expected_status: str) -> None:
        pending = deepcopy(self._record(run_id).snapshot.get("pending_review"))
        before = len(self._record(run_id).events)
        super().resume(run_id, item_id, value, expected_status)
        record = self._record(run_id)
        if pending:
            approved = value.get(item_id) == "approved" if isinstance(value, dict) else False
            self._audit_review_decision(
                record, pending["artifact_ref"]["id"], item_id, approved
            )
        self.repository.save_run(record.snapshot, record.request)
        for kind, event in record.events[before:]:
            self.repository.append_event(run_id, kind, event)

    def cancel(self, run_id: str) -> None:
        before = len(self._record(run_id).events)
        super().cancel(run_id)
        record = self._record(run_id)
        self.repository.save_run(record.snapshot, record.request)
        for kind, event in record.events[before:]:
            self.repository.append_event(run_id, kind, event)

    def _checkpointer(self) -> Any:
        if self._durable_checkpointer is None:
            self._durable_checkpointer = checkpointer_from_database_url(self.database_url)
        return self._durable_checkpointer

    def execute_queued(self, run_id: str) -> None:
        record = self.refresh_run(run_id)
        if record.snapshot["status"] != RunStatus.QUEUED.value:
            return
        before = len(record.events)
        session = self.get_session(record.snapshot["session_id"])
        self._execute(record, session)
        self.repository.save_run(record.snapshot, record.request)
        for kind, event in record.events[before:]:
            self.repository.append_event(run_id, kind, event)

    def resume_queued(self, run_id: str, item_id: str, value: Any, expected_status: str) -> None:
        record = self.refresh_run(run_id)
        pending_review = deepcopy(record.snapshot.get("pending_review"))
        if record.snapshot["status"] != expected_status:
            raise HTTPException(status_code=409, detail="run is not awaiting this interaction")
        pending_key = (
            "pending_review" if expected_status == "awaiting_review" else "pending_clarification"
        )
        pending = record.snapshot.get(pending_key)
        if not pending or pending.get("id") != item_id:
            raise HTTPException(status_code=409, detail="interaction is no longer pending")
        before = len(record.events)
        self._dispatch_resume(record, item_id, value)
        if pending_review:
            approved = value.get(item_id) == "approved" if isinstance(value, dict) else False
            self._audit_review_decision(
                record, pending_review["artifact_ref"]["id"], item_id, approved
            )
        record.snapshot.pop("_queued_resume", None)
        self.repository.save_run(record.snapshot, record.request)
        for kind, event in record.events[before:]:
            self.repository.append_event(run_id, kind, event)

    def audit_entries(self, run_id: str) -> tuple[list[dict[str, Any]], bool]:
        from cellxp.storage.audit_repository import AuditRepository

        self.get_run(run_id)
        with self._factory() as db:
            repo = AuditRepository(db)
            return (
                [entry.model_dump(mode="json") for entry in repo.query(run_id=run_id)],
                repo.verify_chain(run_id=run_id),
            )

    def audit_export(self, run_id: str, artifact_id: str, payload: dict[str, Any]) -> None:
        from cellxp.domain.audit import SYSTEM_ACTOR, AuditEventType
        from cellxp.storage.audit_repository import AuditRepository

        snapshot = self.get_run(run_id)
        with self._factory.begin() as db:
            AuditRepository(db).append(
                event_type=AuditEventType.SIDE_EFFECT_PERFORMED, actor=SYSTEM_ACTOR,
                run_id=run_id, session_id=snapshot["session_id"], subject_ref=artifact_id,
                payload=payload,
            )

    def record_export(self, artifact_id: str, descriptor: dict[str, Any]) -> None:
        for snapshot, request in self.repository.runs():
            for artifact in snapshot.get("artifacts", []):
                if artifact.get("id") == artifact_id:
                    artifact.setdefault("exports", []).append(deepcopy(descriptor))
                    self.repository.save_run(snapshot, request)
                    with self._lock:
                        self.runs[snapshot["id"]] = RunRecord(
                            snapshot=snapshot, request=request,
                            events=self.repository.events_after(snapshot["id"], 0),
                        )
                    return
        raise HTTPException(status_code=404, detail="artifact not found")


class QueuedRuntime(DurableRuntime):
    """Production API runtime: persist identities and enqueue; never invoke LangGraph inline."""

    def __init__(self, database_url: str, redis_url: str, stream: str, group: str) -> None:
        from cellxp.jobs.queues import RedisJobQueue

        super().__init__(database_url)
        self.queue = RedisJobQueue.from_url(redis_url, stream=stream, group=group)
        self.queue.setup()

    def _dispatch_start(self, record: RunRecord, session: SessionSummary) -> None:
        from cellxp.jobs.tasks import GRAPH_START, graph_command

        del session
        try:
            self.queue.enqueue(
                GRAPH_START, graph_command(record.snapshot["id"]),
                job_id=f"start:{record.snapshot['id']}",
            )
        except Exception as exc:
            raise HTTPException(status_code=503, detail="graph queue unavailable") from exc

    def resume(self, run_id: str, item_id: str, value: Any, expected_status: str) -> None:
        from cellxp.jobs.tasks import GRAPH_RESUME, graph_command

        record = self.refresh_run(run_id)
        if record.snapshot["status"] != expected_status:
            raise HTTPException(status_code=409, detail="run is not awaiting this interaction")
        pending_key = "pending_review" if expected_status == "awaiting_review" else "pending_clarification"
        pending = record.snapshot.get(pending_key)
        if not pending or pending.get("id") != item_id:
            raise HTTPException(status_code=409, detail="interaction is no longer pending")
        record.snapshot["_queued_resume"] = {"item_id": item_id, "value": value}
        self.repository.save_run(record.snapshot, record.request)
        try:
            self.queue.enqueue(
                GRAPH_RESUME,
                graph_command(
                    run_id, item_id=item_id, value=value, expected_status=expected_status
                ),
                job_id=f"resume:{run_id}:{item_id}",
            )
        except Exception as exc:
            raise HTTPException(status_code=503, detail="graph queue unavailable") from exc

    def cancel(self, run_id: str) -> None:
        from cellxp.jobs.tasks import GRAPH_CANCEL, graph_command

        self.refresh_run(run_id)
        super().cancel(run_id)
        self.queue.enqueue(
            GRAPH_CANCEL, graph_command(run_id), job_id=f"cancel:{run_id}"
        )

    def _record(self, run_id: str) -> RunRecord:
        return self.refresh_run(run_id)

    def events_after(self, run_id: str, sequence: int) -> list[tuple[str, RunEvent]]:
        if self.repository.run(run_id) is None:
            raise HTTPException(status_code=404, detail="run not found")
        return self.repository.events_after(run_id, sequence)


def create_runtime() -> LocalRuntime:
    from cellxp.config.settings import Settings

    settings = Settings()
    if settings.runtime_backend in {"durable", "queued"}:
        settings.prepare_local_paths()
        if settings.runtime_backend == "queued":
            return QueuedRuntime(
                settings.database_url, settings.redis_url,
                settings.graph_job_stream, settings.graph_consumer_group,
            )
        return DurableRuntime(settings.database_url)
    return LocalRuntime()


runtime = create_runtime()
