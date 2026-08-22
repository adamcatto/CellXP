"""Bounded skill wrappers for legacy LangGraph capability nodes (SKILL-8).

This module is a migration seam, not a model-facing graph-state API. It constructs the minimal
legacy state internally and immediately maps the node update back to ``SkillResult``.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, cast

from pydantic import BaseModel, Field

from cellxp.agent.state import (
    AgentState,
    ExecutionCursor,
    NormalizedInputs,
    RunError,
    Step,
    Subtask,
)
from cellxp.domain.artifacts import ArtifactRef
from cellxp.domain.evidence import EvidenceItem
from cellxp.harness.contracts import (
    SkillContext,
    SkillKind,
    SkillOutcome,
    SkillPlugin,
    SkillResult,
    SkillSideEffect,
    SkillSpec,
)
from cellxp.harness.registry import SkillRegistry

LegacyNode = Callable[[AgentState], dict[str, object]]


class CapabilitySkillInput(BaseModel):
    """Bounded capability input; no transcript or raw ``AgentState`` crosses the tool boundary."""

    normalized_inputs: NormalizedInputs
    subtask: Subtask
    query_summary: str | None = Field(default=None, max_length=2_000)
    prior_evidence: list[EvidenceItem] = Field(default_factory=list)
    prior_artifacts: list[ArtifactRef] = Field(default_factory=list)


class CapabilitySkillOutput(BaseModel):
    subtasks: list[Subtask] = Field(default_factory=list)


def _models(model: type[BaseModel], values: object) -> list[Any]:
    if not isinstance(values, list):
        return []
    return [model.model_validate(value) for value in values]


def legacy_capability_plugin(
    *,
    name: str,
    node: LegacyNode,
    actionable: bool = False,
    requires_coordinate_context: bool = False,
) -> SkillPlugin:
    """Wrap one capability node behind a typed, policy-enforced skill contract."""

    def invoke(arguments: BaseModel, context: SkillContext) -> SkillResult:
        request = CapabilitySkillInput.model_validate(arguments)
        state: dict[str, object] = {
            "run_id": context.run_id,
            "session_type": context.session_type,
            "review_posture": context.review_posture,
            "budget": context.budget,
            "normalized_inputs": request.normalized_inputs,
            "subtasks": [request.subtask],
            "cursor": ExecutionCursor(active_subtask_id=request.subtask.id),
            "evidence": request.prior_evidence,
            "artifacts": request.prior_artifacts,
        }
        if request.query_summary is not None:
            state["user_query"] = request.query_summary
        if context.risk is not None:
            state["risk"] = context.risk

        update = node(cast(AgentState, state))
        steps = cast(list[Step], _models(Step, update.get("steps", [])))
        evidence = cast(list[EvidenceItem], _models(EvidenceItem, update.get("evidence", [])))
        artifacts = cast(list[ArtifactRef], _models(ArtifactRef, update.get("artifacts", [])))
        errors = cast(list[RunError], _models(RunError, update.get("errors", [])))
        subtasks = cast(list[Subtask], _models(Subtask, update.get("subtasks", [])))

        if not update:
            outcome = SkillOutcome.EMPTY
        elif errors:
            outcome = SkillOutcome.RECOVERABLE_FAILURE
        else:
            outcome = SkillOutcome.SUCCESS
        return SkillResult(
            outcome=outcome,
            data=CapabilitySkillOutput(subtasks=subtasks).model_dump(mode="json"),
            steps=steps,
            evidence=evidence,
            artifacts=artifacts,
            errors=errors,
        )

    return SkillPlugin(
        spec=SkillSpec(
            name=f"cellxp.{name}",
            version="0.1.0",
            description=f"Run CellXP's typed {name.replace('_', ' ')} biological capability.",
            kind=SkillKind.CAPABILITY,
            side_effect=(
                SkillSideEffect.ACTIONABLE if actionable else SkillSideEffect.READ
            ),
            implementation=f"langgraph_compatibility:{name}",
            requires_coordinate_context=requires_coordinate_context,
        ),
        input_model=CapabilitySkillInput,
        output_model=CapabilitySkillOutput,
        handler=invoke,
    )


def production_compatibility_registry() -> SkillRegistry:
    """Project implemented capability nodes into the migration registry."""

    from cellxp.agent.graph import production_capability_nodes

    actionable = {"crispr", "inverse_design", "origami"}
    positioned = {"annotation", "binding", "crispr", "gwas", "inverse_design", "variant_effect"}
    registry = SkillRegistry()
    for node_name, node in production_capability_nodes().items():
        name = node_name.removesuffix("_subgraph")
        registry.register(
            legacy_capability_plugin(
                name=name,
                node=node,
                actionable=name in actionable,
                requires_coordinate_context=name in positioned,
            )
        )
    return registry


__all__ = [
    "CapabilitySkillInput",
    "CapabilitySkillOutput",
    "LegacyNode",
    "legacy_capability_plugin",
    "production_compatibility_registry",
]
