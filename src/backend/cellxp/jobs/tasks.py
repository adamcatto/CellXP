"""Versioned command names and payload helpers for detached graph execution."""

from __future__ import annotations

from typing import Any

GRAPH_START = "graph.start.v1"
GRAPH_RESUME = "graph.resume.v1"
GRAPH_CANCEL = "graph.cancel.v1"


def graph_command(run_id: str, **values: Any) -> dict[str, Any]:
    return {"schema_version": "1.0", "run_id": run_id, **values}
