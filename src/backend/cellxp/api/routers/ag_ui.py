"""CopilotKit-facing AG-UI endpoint."""

from __future__ import annotations

from ag_ui.core import RunAgentInput
from ag_ui.encoder import EventEncoder
from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from cellxp.api.ag_ui import ag_ui_event_stream
from cellxp.api.runtime import runtime

router = APIRouter(tags=["ag-ui"])


@router.post("/ag-ui")
async def run_agent(run_input: RunAgentInput, request: Request) -> StreamingResponse:
    encoder = EventEncoder(accept=request.headers.get("accept"))

    async def frames():
        async for event in ag_ui_event_stream(runtime, run_input):
            yield encoder.encode(event)

    return StreamingResponse(
        frames(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "X-Accel-Buffering": "no",
        },
    )
