"""Harness-neutral skill and adapter contracts (ADR-0008, SKILL-1..7)."""

from __future__ import annotations

from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Protocol

from pydantic import BaseModel, Field

from cellxp.agent.state import Budget, RunError, Step
from cellxp.domain.artifacts import ArtifactRef
from cellxp.domain.evidence import EvidenceItem
from cellxp.domain.safety import RiskAssessment


class SkillKind(StrEnum):
    CAPABILITY = "capability"
    WORKFLOW = "workflow"
    TRANSFORM = "transform"
    RESEARCH = "research"
    CODING = "coding"


class SkillSideEffect(StrEnum):
    NONE = "none"
    READ = "read"
    WRITE = "write"
    ACTIONABLE = "actionable"


class SkillOutcome(StrEnum):
    SUCCESS = "success"
    EMPTY = "empty"
    UNSUPPORTED = "unsupported"
    RECOVERABLE_FAILURE = "recoverable_failure"
    POLICY_DENIED = "policy_denied"


class SkillRelease(StrEnum):
    RELEASABLE = "releasable"
    AWAITING_REVIEW = "awaiting_review"


class SkillSpec(BaseModel):
    """Stable, serializable metadata projected to harness tool discovery."""

    name: str = Field(pattern=r"^[a-z][a-z0-9_.-]*$")
    version: str = Field(pattern=r"^[0-9]+\.[0-9]+\.[0-9]+(?:[-+][a-zA-Z0-9.-]+)?$")
    description: str = Field(min_length=1)
    kind: SkillKind
    side_effect: SkillSideEffect = SkillSideEffect.READ
    implementation: str
    requires_risk_assessment: bool = True
    requires_coordinate_context: bool = False
    requires_provenance: bool = True
    model_visible: bool = True


class SkillContext(BaseModel):
    """Kernel-owned context; it is never supplied by model tool arguments."""

    session_id: str
    run_id: str
    actor_id: str = "agent"
    session_type: str = "general"
    review_posture: str = "standard"
    risk: RiskAssessment | None = None
    budget: Budget = Field(default_factory=Budget)
    workspace_refs: list[str] = Field(default_factory=list)
    approved_subject_ids: set[str] = Field(default_factory=set)


class SkillInvocation(BaseModel):
    skill_name: str
    skill_version: str | None = None
    arguments: dict[str, Any] = Field(default_factory=dict)
    context: SkillContext


class SkillResult(BaseModel):
    """Canonical result returned to storage/event projection, not directly to a model."""

    outcome: SkillOutcome = SkillOutcome.SUCCESS
    data: Any = None
    detail: str | None = None
    steps: list[Step] = Field(default_factory=list)
    evidence: list[EvidenceItem] = Field(default_factory=list)
    artifacts: list[ArtifactRef] = Field(default_factory=list)
    errors: list[RunError] = Field(default_factory=list)
    release: SkillRelease = SkillRelease.RELEASABLE
    review_subject_ids: list[str] = Field(default_factory=list)


SkillHandler = Callable[
    [BaseModel, SkillContext],
    SkillResult | Awaitable[SkillResult],
]


@dataclass(frozen=True, slots=True)
class SkillPlugin:
    spec: SkillSpec
    input_model: type[BaseModel]
    handler: SkillHandler

    def tool_definition(self) -> dict[str, Any]:
        """Project the bounded input model to an OpenAI/MCP-compatible tool definition."""

        return {
            "name": self.spec.name,
            "description": self.spec.description,
            "inputSchema": self.input_model.model_json_schema(),
            "metadata": {
                "version": self.spec.version,
                "kind": self.spec.kind.value,
                "sideEffect": self.spec.side_effect.value,
            },
        }


class PolicyHook(Protocol):
    """Authoritative kernel hook; harness-native hooks are only advisory mirrors."""

    def before(
        self,
        plugin: SkillPlugin,
        invocation: SkillInvocation,
        arguments: BaseModel,
    ) -> None: ...

    def after(
        self,
        plugin: SkillPlugin,
        invocation: SkillInvocation,
        result: SkillResult,
    ) -> SkillResult: ...


class HarnessEvent(BaseModel):
    type: str
    data: dict[str, Any] = Field(default_factory=dict)


class HarnessAdapter(Protocol):
    """Adapter seam for Qwen Code and future mature agent harnesses."""

    name: str

    def stream_turn(
        self,
        *,
        session_id: str,
        run_id: str,
        prompt: str,
        context_refs: list[str],
    ) -> AsyncIterator[HarnessEvent]: ...


__all__ = [
    "HarnessAdapter",
    "HarnessEvent",
    "PolicyHook",
    "SkillContext",
    "SkillHandler",
    "SkillInvocation",
    "SkillKind",
    "SkillOutcome",
    "SkillPlugin",
    "SkillRelease",
    "SkillResult",
    "SkillSideEffect",
    "SkillSpec",
]
