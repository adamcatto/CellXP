"""AG-UI projection over CellXP's canonical session and run runtime.

The adapter deliberately keeps CellXP IDs, artifacts, review policy, and persistence authoritative.
It translates protocol input into the existing runtime and projects bounded references back to the
browser; it never exposes graph state or artifact payloads.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator, Iterable
from copy import deepcopy
from typing import Any

from ag_ui.core import (
    BaseEvent,
    Interrupt,
    RunAgentInput,
    RunErrorEvent,
    RunFinishedEvent,
    RunFinishedInterruptOutcome,
    RunFinishedSuccessOutcome,
    RunStartedEvent,
    StateSnapshotEvent,
    TextMessageContentEvent,
    TextMessageEndEvent,
    TextMessageStartEvent,
    ToolCallArgsEvent,
    ToolCallEndEvent,
    ToolCallResultEvent,
    ToolCallStartEvent,
)
from fastapi import HTTPException

from cellxp.api.runtime import LocalRuntime
from cellxp.api.schemas import ClarificationAnswerRequest, CreateRunRequest, ReviewDecisionRequest

TERMINAL_STATUSES = {"awaiting_input", "awaiting_review", "completed", "failed", "cancelled"}
MAX_CONTEXT_ARTIFACTS = 20
MAX_PROJECTED_ARTIFACTS = 50
MAX_PROJECTED_EVIDENCE = 50
WORKSPACE_CONTEXT_DESCRIPTION = "CellXP workspace context"


def _as_json(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json", by_alias=True, exclude_none=True)
    return deepcopy(value)


def _message_text(message: Any) -> str | None:
    """Return bounded text from an AG-UI user message, ignoring binary attachment bodies."""
    content = getattr(message, "content", None)
    if isinstance(content, str):
        return content.strip() or None
    if not isinstance(content, list):
        return None

    parts: list[str] = []
    for item in content:
        raw = _as_json(item)
        if isinstance(raw, dict) and raw.get("type") == "text" and isinstance(raw.get("text"), str):
            parts.append(raw["text"])
    text = "\n".join(parts).strip()
    return text or None


def latest_user_message(run_input: RunAgentInput) -> str:
    for message in reversed(run_input.messages):
        if getattr(message, "role", None) == "user" and (text := _message_text(message)):
            return text
    raise HTTPException(status_code=422, detail="AG-UI input contains no user text message")


def _workspace_from_input(run_input: RunAgentInput) -> dict[str, Any]:
    state = run_input.state
    if isinstance(state, dict) and isinstance(state.get("workspace"), dict):
        return deepcopy(state["workspace"])

    for context in reversed(run_input.context):
        if context.description != WORKSPACE_CONTEXT_DESCRIPTION:
            continue
        try:
            parsed = json.loads(context.value)
        except (TypeError, json.JSONDecodeError):
            return {}
        return parsed if isinstance(parsed, dict) else {}
    return {}


def _artifact_ids(workspace: dict[str, Any]) -> list[str]:
    values = workspace.get("selected_artifact_ids", [])
    if not isinstance(values, list):
        raise HTTPException(status_code=422, detail="selected_artifact_ids must be an array")
    result = list(dict.fromkeys(item for item in values if isinstance(item, str) and item))
    if len(result) > MAX_CONTEXT_ARTIFACTS:
        raise HTTPException(
            status_code=422,
            detail=f"at most {MAX_CONTEXT_ARTIFACTS} artifact references may enter one run",
        )
    return result


def authorize_artifact_refs(
    runtime: LocalRuntime, session_id: str, artifact_ids: Iterable[str]
) -> list[str]:
    """Fail closed when a UI-supplied artifact reference is outside the current session."""
    authorized: list[str] = []
    for artifact_id in artifact_ids:
        snapshot, _ = runtime.find_artifact(artifact_id)
        if snapshot["session_id"] != session_id:
            raise HTTPException(status_code=403, detail="artifact reference is outside this session")
        authorized.append(artifact_id)
    return authorized


def _bounded_artifact(item: dict[str, Any]) -> dict[str, Any]:
    keys = (
        "id",
        "run_id",
        "type",
        "title",
        "status",
        "summary",
        "actionable",
        "review_status",
        "created_at",
    )
    return {key: deepcopy(item[key]) for key in keys if key in item}


def _bounded_evidence(item: dict[str, Any]) -> dict[str, Any]:
    keys = ("id", "kind", "source", "title", "summary", "confidence", "step_id", "retrieved_at")
    return {key: deepcopy(item[key]) for key in keys if key in item}


def project_state(
    snapshot: dict[str, Any], workspace: dict[str, Any] | None = None
) -> dict[str, Any]:
    """Build the intentionally small browser-visible state projection."""
    pending: dict[str, Any] | None = None
    if snapshot.get("pending_clarification"):
        pending = {
            "kind": "clarification",
            "value": deepcopy(snapshot["pending_clarification"]),
        }
    elif snapshot.get("pending_review"):
        pending = {"kind": "review", "value": deepcopy(snapshot["pending_review"])}

    cellxp: dict[str, Any] = {
        "session_id": snapshot["session_id"],
        "run_id": snapshot["id"],
        "status": snapshot["status"],
        "artifacts": [
            _bounded_artifact(item)
            for item in snapshot.get("artifacts", [])[-MAX_PROJECTED_ARTIFACTS:]
        ],
        "evidence": [
            _bounded_evidence(item)
            for item in snapshot.get("evidence", [])[-MAX_PROJECTED_EVIDENCE:]
        ],
        "pending_interaction": pending,
        "model": {
            "provider": snapshot.get("provider"),
            "name": snapshot.get("model"),
        },
    }
    if snapshot.get("plan"):
        cellxp["plan"] = deepcopy(snapshot["plan"])

    return {
        "cellxp": cellxp,
        "workspace": deepcopy(workspace or {}),
    }


def _tool_events(snapshot: dict[str, Any]) -> Iterable[BaseEvent]:
    run_id = snapshot["id"]
    for step in snapshot.get("steps", []):
        tool_call_id = f"step:{step['id']}"
        yield ToolCallStartEvent(
            tool_call_id=tool_call_id,
            tool_call_name=step.get("tool") or "cellxp_tool",
        )
        yield ToolCallArgsEvent(
            tool_call_id=tool_call_id,
            delta=json.dumps(
                {
                    "step": {
                        key: step.get(key)
                        for key in ("id", "label", "status", "tool_version", "input_summary")
                    }
                },
                separators=(",", ":"),
            ),
        )
        yield ToolCallEndEvent(tool_call_id=tool_call_id)
        yield ToolCallResultEvent(
            message_id=f"tool-result:{step['id']}",
            tool_call_id=tool_call_id,
            content=json.dumps(
                {
                    "run_id": run_id,
                    "status": step.get("status"),
                    "output_summary": step.get("output_summary"),
                    "artifact_ids": step.get("artifact_ids", []),
                    "evidence_ids": step.get("evidence_ids", []),
                },
                separators=(",", ":"),
            ),
        )

    for artifact in snapshot.get("artifacts", []):
        tool_call_id = f"artifact:{artifact['id']}"
        yield ToolCallStartEvent(
            tool_call_id=tool_call_id,
            tool_call_name="render_cellxp_artifact",
        )
        yield ToolCallArgsEvent(
            tool_call_id=tool_call_id,
            delta=json.dumps(
                {"artifact": _bounded_artifact(artifact)},
                separators=(",", ":"),
            ),
        )
        yield ToolCallEndEvent(tool_call_id=tool_call_id)
        yield ToolCallResultEvent(
            message_id=f"artifact-result:{artifact['id']}",
            tool_call_id=tool_call_id,
            content=json.dumps(
                {"artifact_id": artifact["id"], "status": artifact.get("status", "ready")},
                separators=(",", ":"),
            ),
        )


def _interrupt_for(snapshot: dict[str, Any]) -> Interrupt | None:
    if clarification := snapshot.get("pending_clarification"):
        return Interrupt(
            id=clarification["id"],
            reason="input_required",
            message=clarification["question"],
            response_schema={
                "type": "object",
                "properties": {
                    "selected_option_ids": {"type": "array", "items": {"type": "string"}},
                    "freeform": {"type": ["string", "null"]},
                },
                "additionalProperties": False,
            },
            metadata={
                "kind": "clarification",
                "run_id": snapshot["id"],
                "clarification": deepcopy(clarification),
            },
        )
    if review := snapshot.get("pending_review"):
        return Interrupt(
            id=review["id"],
            reason="confirmation",
            message="Review this actionable biological output before it can be used.",
            response_schema={
                "type": "object",
                "properties": {
                    "decision": {
                        "type": "string",
                        "enum": ["approve", "reject", "request_changes"],
                    },
                    "note": {"type": ["string", "null"]},
                },
                "required": ["decision"],
                "additionalProperties": False,
            },
            metadata={
                "kind": "review",
                "run_id": snapshot["id"],
                "review": deepcopy(review),
            },
        )
    return None


def snapshot_events(
    run_input: RunAgentInput,
    snapshot: dict[str, Any],
    workspace: dict[str, Any] | None = None,
) -> Iterable[BaseEvent]:
    """Project one settled CellXP snapshot into an ordered AG-UI event sequence."""
    yield StateSnapshotEvent(snapshot=project_state(snapshot, workspace))
    yield from _tool_events(snapshot)

    if report := snapshot.get("report"):
        message_id = f"report:{snapshot['id']}"
        yield TextMessageStartEvent(message_id=message_id, role="assistant")
        yield TextMessageContentEvent(message_id=message_id, delta=report)
        yield TextMessageEndEvent(message_id=message_id)

    # Emit a final state after messages/tool calls so clients finish with canonical IDs and status.
    yield StateSnapshotEvent(snapshot=project_state(snapshot, workspace))

    if snapshot["status"] == "failed":
        error = next(
            (item for item in snapshot.get("errors", []) if item.get("fatal")),
            {"code": "run_failed", "message": "CellXP run failed."},
        )
        yield RunErrorEvent(message=error["message"], code=error.get("code"))
        return

    if interrupt := _interrupt_for(snapshot):
        yield RunFinishedEvent(
            thread_id=run_input.thread_id,
            run_id=run_input.run_id,
            result={"cellxpRunId": snapshot["id"], "status": snapshot["status"]},
            outcome=RunFinishedInterruptOutcome(interrupts=[interrupt]),
        )
        return

    yield RunFinishedEvent(
        thread_id=run_input.thread_id,
        run_id=run_input.run_id,
        result={"cellxpRunId": snapshot["id"], "status": snapshot["status"]},
        outcome=RunFinishedSuccessOutcome(),
    )


def _resume_value(snapshot: dict[str, Any], interrupt_id: str, payload: Any) -> tuple[Any, str]:
    if pending := snapshot.get("pending_clarification"):
        if pending["id"] != interrupt_id:
            raise HTTPException(status_code=409, detail="clarification is no longer pending")
        answer = ClarificationAnswerRequest.model_validate(payload or {})
        return answer.model_dump(mode="json"), "awaiting_input"

    if pending := snapshot.get("pending_review"):
        if pending["id"] != interrupt_id:
            raise HTTPException(status_code=409, detail="review is no longer pending")
        raw = dict(payload) if isinstance(payload, dict) else {}
        raw.setdefault("expected_run_status", "awaiting_review")
        decision = ReviewDecisionRequest.model_validate(raw)
        values = {"approve": "approved", "reject": "rejected", "request_changes": "rejected"}
        return {interrupt_id: values[decision.decision]}, "awaiting_review"

    raise HTTPException(status_code=409, detail="run has no pending interaction")


def start_or_resume(
    runtime: LocalRuntime, run_input: RunAgentInput
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Apply one AG-UI turn and return the canonical snapshot plus bounded UI workspace state."""
    workspace = _workspace_from_input(run_input)

    if run_input.resume:
        state = run_input.state if isinstance(run_input.state, dict) else {}
        raw_cellxp_state = state.get("cellxp")
        cellxp_state = raw_cellxp_state if isinstance(raw_cellxp_state, dict) else {}
        cellxp_run_id = cellxp_state.get("run_id")
        if not isinstance(cellxp_run_id, str) or not cellxp_run_id:
            raise HTTPException(status_code=422, detail="resume requires cellxp.run_id in state")
        snapshot = runtime.get_run(cellxp_run_id)
        if snapshot["session_id"] != run_input.thread_id:
            raise HTTPException(status_code=403, detail="run is outside this session")
        if len(run_input.resume) != 1:
            raise HTTPException(status_code=422, detail="CellXP accepts one pending interaction at a time")

        entry = run_input.resume[0]
        if snapshot["status"] in {"completed", "failed", "cancelled"}:
            return snapshot, workspace
        if entry.status == "cancelled":
            runtime.cancel(cellxp_run_id)
        else:
            value, expected_status = _resume_value(snapshot, entry.interrupt_id, entry.payload)
            runtime.resume(cellxp_run_id, entry.interrupt_id, value, expected_status)
        return runtime.get_run(cellxp_run_id), workspace

    artifact_ids = authorize_artifact_refs(
        runtime, run_input.thread_id, _artifact_ids(workspace)
    )
    request = CreateRunRequest(
        message=latest_user_message(run_input),
        referenced_artifact_ids=artifact_ids,
        client_request_id=run_input.run_id,
    )
    response = runtime.create_run(run_input.thread_id, request)
    return runtime.get_run(response.run_id), workspace


async def ag_ui_event_stream(
    runtime: LocalRuntime,
    run_input: RunAgentInput,
    *,
    poll_interval_seconds: float = 0.25,
) -> AsyncIterator[BaseEvent]:
    """Run or resume CellXP and yield standard AG-UI events.

    Queued production runs are observed until they settle. Progressive node-level translation remains
    a later optimization; the current runtime only guarantees reconstructable terminal snapshots.
    """
    yield RunStartedEvent(
        thread_id=run_input.thread_id,
        run_id=run_input.run_id,
        parent_run_id=run_input.parent_run_id,
    )
    try:
        snapshot, workspace = start_or_resume(runtime, run_input)
        while snapshot["status"] not in TERMINAL_STATUSES:
            await asyncio.sleep(poll_interval_seconds)
            snapshot = runtime.get_run(snapshot["id"])
        for event in snapshot_events(run_input, snapshot, workspace):
            yield event
    except HTTPException as exc:
        yield RunErrorEvent(message=str(exc.detail), code=f"http_{exc.status_code}")
    except Exception:  # noqa: BLE001 - protocol boundary converts all internals to a safe error
        # The protocol boundary must not expose raw exceptions, paths, model payloads, or credentials.
        yield RunErrorEvent(message="CellXP could not complete this agent run.", code="adapter_error")
