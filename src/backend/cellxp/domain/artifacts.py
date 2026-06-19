"""In-state artifact references.

The compact `ArtifactRef` is what flows in `AgentState.artifacts` (`state_schema.md` §10):
state carries only the reference + a bounded preview, never large payloads (ART-2). The
full `ArtifactManifest` (payload schema, coordinate frame, exports, accessibility) is an
interface/visualization-service concern (`artifact_model.md` §2) and is built there.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from .clock import utc_now_iso
from .enums import ArtifactType
from .ids import new_id


class ArtifactRef(BaseModel):
    """Lightweight reference to a produced artifact (`state_schema.md` §10).

    `actionable` artifacts (e.g. a guide table) are gated by the human-review state (§12);
    `evidence_ids` link the artifact back to the evidence that produced it (ART-1/PROV-2).
    """

    id: str = Field(default_factory=new_id)
    type: ArtifactType
    title: str
    subtask_id: str | None = None
    storage_ref: str | None = None  # object-store key for heavy payloads (ART-2)
    summary: dict[str, Any] = Field(default_factory=dict)  # bounded inline preview
    evidence_ids: list[str] = Field(default_factory=list)
    actionable: bool = False
    created_at: str = Field(default_factory=utc_now_iso)
