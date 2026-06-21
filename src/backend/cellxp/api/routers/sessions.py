"""Session/workspace endpoints for API v1."""

from fastapi import APIRouter, Response, status

from cellxp.api.runtime import runtime
from cellxp.api.schemas import CreateSessionRequest, PatchSessionRequest, SessionSummary

router = APIRouter(prefix="/sessions", tags=["sessions"])


@router.post("", response_model=SessionSummary, status_code=status.HTTP_201_CREATED)
def create_session(request: CreateSessionRequest) -> SessionSummary:
    return runtime.create_session(request)


@router.get("")
def list_sessions() -> dict[str, object]:
    return {"items": runtime.list_sessions(), "next_cursor": None}


@router.get("/{session_id}", response_model=SessionSummary)
def get_session(session_id: str) -> SessionSummary:
    return runtime.get_session(session_id)


@router.patch("/{session_id}", response_model=SessionSummary)
def patch_session(session_id: str, request: PatchSessionRequest) -> SessionSummary:
    return runtime.patch_session(session_id, request)


@router.delete("/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_session(session_id: str) -> Response:
    runtime.delete_session(session_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/{session_id}/runs")
def list_session_runs(session_id: str) -> dict[str, object]:
    return {"items": runtime.list_runs(session_id), "next_cursor": None}


@router.get("/{session_id}/artifacts")
def list_session_artifacts(session_id: str) -> dict[str, object]:
    items = [artifact for run in runtime.list_runs(session_id) for artifact in run["artifacts"]]
    return {"items": items, "next_cursor": None}


@router.get("/{session_id}/files")
def list_session_files(session_id: str) -> dict[str, object]:
    runtime.get_session(session_id)
    return {"items": [], "next_cursor": None}
