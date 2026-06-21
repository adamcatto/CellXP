"""Run lifecycle and ordered SSE endpoints for API v1."""

from __future__ import annotations

import json

from fastapi import APIRouter, Header, Query, Response, status
from fastapi.responses import StreamingResponse

from cellxp.api.runtime import runtime
from cellxp.api.schemas import (
    ClarificationAnswerRequest,
    CreateRunRequest,
    CreateRunResponse,
    ReviewDecisionRequest,
)
from cellxp.domain.ids import new_id

router = APIRouter(tags=["runs"])


@router.post(
    "/sessions/{session_id}/runs", response_model=CreateRunResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def create_run(session_id: str, request: CreateRunRequest) -> CreateRunResponse:
    return runtime.create_run(session_id, request)


@router.get("/runs/{run_id}")
def get_run(run_id: str) -> dict[str, object]:
    return runtime.get_run(run_id)


@router.post("/runs/{run_id}/cancel", status_code=status.HTTP_204_NO_CONTENT)
def cancel_run(run_id: str) -> Response:
    runtime.cancel(run_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/runs/{run_id}/reproduce", response_model=CreateRunResponse)
def reproduce_run(run_id: str) -> CreateRunResponse:
    source = runtime._record(run_id)
    request = source.request.model_copy(update={"client_request_id": new_id()}, deep=True)
    return runtime.create_run(
        source.snapshot["session_id"], request, reproduces_run_id=run_id
    )


@router.get("/runs/{run_id}/steps")
def list_steps(run_id: str) -> dict[str, object]:
    return {"items": runtime.get_run(run_id)["steps"], "next_cursor": None}


@router.get("/runs/{run_id}/evidence")
def list_evidence(run_id: str) -> dict[str, object]:
    return {"items": runtime.get_run(run_id)["evidence"], "next_cursor": None}


@router.post(
    "/runs/{run_id}/clarifications/{clarification_id}/answer",
    status_code=status.HTTP_204_NO_CONTENT,
)
def answer_clarification(
    run_id: str, clarification_id: str, request: ClarificationAnswerRequest
) -> Response:
    runtime.resume(
        run_id, clarification_id, request.model_dump(mode="json"), "awaiting_input"
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/runs/{run_id}/reviews/{review_id}/decision",
    status_code=status.HTTP_204_NO_CONTENT,
)
def decide_review(run_id: str, review_id: str, request: ReviewDecisionRequest) -> Response:
    decisions = {"approve": "approved", "reject": "rejected", "request_changes": "rejected"}
    runtime.resume(run_id, review_id, {review_id: decisions[request.decision]}, "awaiting_review")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/runs/{run_id}/events")
def stream_events(
    run_id: str,
    last_event_id_query: int = Query(default=0, alias="last_event_id", ge=0),
    last_event_id_header: str | None = Header(default=None, alias="Last-Event-ID"),
) -> StreamingResponse:
    try:
        header_sequence = int(last_event_id_header) if last_event_id_header else 0
    except ValueError:
        header_sequence = 0
    sequence = max(last_event_id_query, header_sequence)
    events = runtime.events_after(run_id, sequence)

    def frames():
        for kind, event in events:
            yield (
                f"id: {event.seq}\n"
                f"event: {kind}\n"
                f"data: {json.dumps(event.model_dump(mode='json'), separators=(',', ':'))}\n\n"
            )

    return StreamingResponse(
        frames(), media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
