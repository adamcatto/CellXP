"""Artifact references and manifests.

The compact `ArtifactRef` is what flows in `AgentState.artifacts` (`state_schema.md` §10):
state carries only the reference + a bounded preview, never large payloads (ART-2). The
full `ArtifactManifest` is returned by the artifact API (`artifact_model.md` §2).
"""

from __future__ import annotations

import json
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator

from .clock import utc_now_iso
from .enums import ArtifactType, CoordinateSystem, Strand
from .evidence import Confidence
from .ids import new_id

OBJECT_INLINE_MAX = 16 * 1024


def _json_size(value: Any) -> int:
    """Return the compact UTF-8 JSON size used for inline artifact limits."""

    return len(json.dumps(value, separators=(",", ":"), default=str).encode("utf-8"))


class CoordinateFrame(BaseModel):
    """Coordinate context required to interpret a positioned artifact (ART-5)."""

    kind: Literal["genomic", "sequence", "structure", "shape", "none"]
    organism: str | None = None
    assembly: str | None = None
    contig: str | None = None
    convention: CoordinateSystem | None = None
    strand: Strand | None = None
    circular: bool = False
    chain_map: dict[str, str] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _require_genomic_context(self) -> CoordinateFrame:
        if self.kind == "genomic":
            missing = [
                name
                for name in ("organism", "assembly", "contig", "convention")
                if getattr(self, name) is None
            ]
            if missing:
                raise ValueError(f"genomic coordinate frame requires: {', '.join(missing)}")
            if self.convention is not CoordinateSystem.ZERO_BASED_HALF_OPEN:
                raise ValueError("genomic artifact coordinates must use 0-based-half-open")
        if self.kind == "structure" and not self.chain_map:
            raise ValueError("structure coordinate frame requires a non-empty chain_map")
        return self


class Interaction(BaseModel):
    """Renderer-independent interaction advertised by an artifact."""

    type: Literal[
        "pan", "zoom", "hover", "select", "filter", "sort", "toggle", "link", "measure"
    ]
    target: str | None = None


class ExportDescriptor(BaseModel):
    """One available visual, data, or source export."""

    format: str
    media_type: str
    kind: Literal["visual", "data", "source"]
    ready: bool = True


class AccessibilityMetadata(BaseModel):
    """Non-visual/static fallback metadata required by ART-6."""

    summary: str
    table_available: bool = False
    static_preview_available: bool = False
    keyboard_help: str | None = None


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

    @model_validator(mode="after")
    def _validate_summary_size(self) -> ArtifactRef:
        if _json_size(self.summary) > OBJECT_INLINE_MAX:
            raise ValueError(f"summary exceeds OBJECT_INLINE_MAX ({OBJECT_INLINE_MAX})")
        return self


class ArtifactManifest(BaseModel):
    """Complete, versioned artifact contract returned by the artifact API."""

    id: str = Field(default_factory=new_id)
    schema_version: str = "1.0"
    type: ArtifactType
    payload_schema: str
    title: str
    description: str | None = None
    status: Literal["pending", "ready", "partial", "failed"] = "pending"
    revision: int = Field(default=0, ge=0)

    session_id: str
    run_id: str
    subtask_id: str | None = None
    step_id: str | None = None
    evidence_ids: list[str] = Field(default_factory=list)
    source_artifact_ids: list[str] = Field(default_factory=list)
    supersedes: str | None = None

    summary: dict[str, Any] = Field(default_factory=dict)
    payload: dict[str, Any] | None = None
    storage_ref: str | None = None
    content_type: str | None = None
    content_hash: str | None = None

    coordinate_frame: CoordinateFrame | None = None
    units: dict[str, str] = Field(default_factory=dict)
    confidence: Confidence | None = None
    limitations: list[str] = Field(default_factory=list)
    transform_notes: list[str] = Field(default_factory=list)

    interactions: list[Interaction] = Field(default_factory=list)
    exports: list[ExportDescriptor] = Field(default_factory=list)
    accessibility: AccessibilityMetadata
    actionable: bool = False
    review_status: Literal[
        "not_required", "pending", "approved", "rejected", "changes_requested"
    ] = "not_required"
    created_at: str = Field(default_factory=utc_now_iso)
    updated_at: str = Field(default_factory=utc_now_iso)

    @model_validator(mode="after")
    def _validate_lifecycle_and_size(self) -> ArtifactManifest:
        if self.status == "ready" and self.payload is None and self.storage_ref is None:
            raise ValueError("ready artifact requires an inline payload or storage_ref")
        if self.actionable and self.review_status == "not_required":
            raise ValueError("actionable artifact requires an explicit review status")
        if self.supersedes == self.id:
            raise ValueError("artifact cannot supersede itself")
        for field_name in ("summary", "payload"):
            value = getattr(self, field_name)
            if value is not None and _json_size(value) > OBJECT_INLINE_MAX:
                raise ValueError(f"{field_name} exceeds OBJECT_INLINE_MAX ({OBJECT_INLINE_MAX})")
        if self.payload is not None:
            missing = [name for name in ("schema", "version", "data") if name not in self.payload]
            if missing:
                raise ValueError(f"artifact payload requires: {', '.join(missing)}")
        if self.interactions:
            if not any(export.kind in {"data", "source"} for export in self.exports):
                raise ValueError("interactive artifact requires an underlying-data export")
            if not (
                self.accessibility.table_available
                or self.accessibility.static_preview_available
            ):
                raise ValueError("interactive artifact requires a tabular or static fallback")
        return self

    def to_ref(self) -> ArtifactRef:
        """Return the bounded representation stored in AgentState and SSE payloads."""

        return ArtifactRef(
            id=self.id,
            type=self.type,
            title=self.title,
            subtask_id=self.subtask_id,
            storage_ref=self.storage_ref,
            summary=dict(self.summary),
            evidence_ids=list(self.evidence_ids),
            actionable=self.actionable,
            created_at=self.created_at,
        )
