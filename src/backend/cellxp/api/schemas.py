"""Versioned HTTP schemas for the CellXP v1 API boundary."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator


class Collection(BaseModel):
    items: list[Any] = Field(default_factory=list)
    next_cursor: str | None = None


class SessionDefaults(BaseModel):
    organism: str | None = None
    assembly: str | None = None
    persona: str | None = None
    review_posture: Literal["standard", "strict"] | None = None


class CreateSessionRequest(BaseModel):
    type: str
    title: str = Field(min_length=1, max_length=200)
    defaults: SessionDefaults = Field(default_factory=SessionDefaults)


class PatchSessionRequest(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    defaults: dict[str, Any] | None = None
    expected_revision: int = Field(ge=0)


class SessionSummary(BaseModel):
    id: str
    title: str
    type: str
    defaults: SessionDefaults
    revision: int
    created_at: str
    updated_at: str
    run_count: int = 0
    artifact_count: int = 0


class RawInput(BaseModel):
    kind: str
    value: str | dict[str, Any]
    upload_id: str | None = None


class CreateRunRequest(BaseModel):
    message: str | None = None
    inputs: list[RawInput] = Field(default_factory=list)
    overrides: dict[str, Any] = Field(default_factory=dict)
    referenced_artifact_ids: list[str] = Field(default_factory=list)
    client_request_id: str = Field(min_length=1, max_length=200)

    @model_validator(mode="after")
    def _require_content(self) -> "CreateRunRequest":
        if not self.message and not self.inputs:
            raise ValueError("at least one of message or inputs is required")
        return self


class CreateRunResponse(BaseModel):
    run_id: str
    session_id: str
    status: str
    stream_url: str
    created_at: str


class ClarificationAnswerRequest(BaseModel):
    selected_option_ids: list[str] = Field(default_factory=list)
    freeform: str | None = None


class ReviewDecisionRequest(BaseModel):
    decision: Literal["approve", "reject", "request_changes"]
    note: str | None = None
    expected_run_status: Literal["awaiting_review"]


class RunEvent(BaseModel):
    schema_version: str = "1.0"
    run_id: str
    seq: int
    at: str
    data: dict[str, Any] = Field(default_factory=dict)


class SaveGuidePoolRequest(BaseModel):
    session_id: str
    name: str = Field(default="Guide pool", min_length=1, max_length=200)
    guide_ids: list[str] = Field(min_length=1, max_length=100)
    expected_revision: int | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def _unique_guides(self) -> "SaveGuidePoolRequest":
        if len(set(self.guide_ids)) != len(self.guide_ids):
            raise ValueError("guide_ids must be unique")
        return self


class GuidePoolResponse(BaseModel):
    id: str
    session_id: str
    source_artifact_id: str
    name: str
    guide_ids: list[str]
    revision: int
    created_at: str
    updated_at: str


class ArtifactExportRequest(BaseModel):
    format: str = Field(min_length=1, max_length=32)


class ArtifactExportResponse(BaseModel):
    id: str
    artifact_id: str
    format: str
    media_type: str
    content_hash: str
    status: Literal["ready"] = "ready"


class ArtifactManifestResponse(BaseModel):
    id: str
    schema_version: str = "1.0"
    type: str
    payload_schema: str
    title: str
    status: str
    session_id: str
    run_id: str
    summary: dict[str, Any] = Field(default_factory=dict)
    evidence_ids: list[str] = Field(default_factory=list)
    actionable: bool = False
    review_status: str = "not_required"
    exports: list[dict[str, Any]] = Field(default_factory=list)
    content_available: bool
    storage_ref: None = None


class AuditEntryResponse(BaseModel):
    id: str
    event_type: str
    actor: dict[str, Any]
    run_id: str | None = None
    session_id: str | None = None
    subject_ref: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)
    at: str
    prev_hash: str | None = None
    hash: str


class AuditCollectionResponse(BaseModel):
    items: list[AuditEntryResponse] = Field(default_factory=list)
    chain_valid: bool
    next_cursor: str | None = None
