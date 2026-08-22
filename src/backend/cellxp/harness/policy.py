"""CellXP-owned policy kernel around every harness skill invocation (SKILL-5)."""

from __future__ import annotations

import inspect

from pydantic import BaseModel, ValidationError

from cellxp.agent.state import RunError
from cellxp.harness.contracts import (
    PolicyHook,
    SkillInvocation,
    SkillOutcome,
    SkillPlugin,
    SkillRelease,
    SkillResult,
    SkillSideEffect,
)
from cellxp.harness.registry import SkillRegistry


class SkillPolicyViolation(RuntimeError):
    def __init__(self, code: str, detail: str) -> None:
        super().__init__(detail)
        self.code = code
        self.detail = detail


class SafetyPolicyHook:
    """Fail closed unless biological capability work has passed the risk gate."""

    def before(
        self,
        plugin: SkillPlugin,
        invocation: SkillInvocation,
        arguments: BaseModel,
    ) -> None:
        del arguments
        if not plugin.spec.requires_risk_assessment:
            return
        risk = invocation.context.risk
        if risk is None:
            raise SkillPolicyViolation(
                "risk_assessment_required",
                "Biological skills require a canonical risk assessment before execution.",
            )
        if risk.is_blocked:
            raise SkillPolicyViolation(
                "risk_blocked",
                "The canonical risk assessment blocks capability execution.",
            )

    def after(
        self,
        plugin: SkillPlugin,
        invocation: SkillInvocation,
        result: SkillResult,
    ) -> SkillResult:
        del plugin, invocation
        return result


class ActionableReviewPolicyHook:
    """Withhold actionable results until canonical human review approves each subject."""

    def before(
        self,
        plugin: SkillPlugin,
        invocation: SkillInvocation,
        arguments: BaseModel,
    ) -> None:
        del plugin, invocation, arguments

    def after(
        self,
        plugin: SkillPlugin,
        invocation: SkillInvocation,
        result: SkillResult,
    ) -> SkillResult:
        subjects = [artifact.id for artifact in result.artifacts if artifact.actionable]
        if (
            result.outcome is SkillOutcome.SUCCESS
            and plugin.spec.side_effect is SkillSideEffect.ACTIONABLE
            and not subjects
        ):
            subjects = [f"skill:{plugin.spec.name}"]
        pending = [
            subject
            for subject in subjects
            if subject not in invocation.context.approved_subject_ids
        ]
        if not pending:
            return result
        return result.model_copy(
            update={
                "release": SkillRelease.AWAITING_REVIEW,
                "review_subject_ids": pending,
            }
        )


class ProvenancePolicyHook:
    """Prevent substantive successful tool output without at least one recorded Step."""

    def before(
        self,
        plugin: SkillPlugin,
        invocation: SkillInvocation,
        arguments: BaseModel,
    ) -> None:
        del plugin, invocation, arguments

    def after(
        self,
        plugin: SkillPlugin,
        invocation: SkillInvocation,
        result: SkillResult,
    ) -> SkillResult:
        del invocation
        if (
            plugin.spec.requires_provenance
            and result.outcome is SkillOutcome.SUCCESS
            and not result.steps
        ):
            raise SkillPolicyViolation(
                "missing_provenance",
                f"Skill {plugin.spec.name!r} returned success without a recorded Step.",
            )
        return result


class SkillExecutor:
    """Validate, authorize, invoke, and post-process a registered skill."""

    def __init__(
        self,
        registry: SkillRegistry,
        *,
        hooks: tuple[PolicyHook, ...] | None = None,
    ) -> None:
        self.registry = registry
        self.hooks = hooks or (
            SafetyPolicyHook(),
            ProvenancePolicyHook(),
            ActionableReviewPolicyHook(),
        )

    async def invoke(self, invocation: SkillInvocation) -> SkillResult:
        plugin = self.registry.get(invocation.skill_name, invocation.skill_version)
        try:
            arguments = plugin.input_model.model_validate(invocation.arguments)
        except ValidationError as exc:
            return SkillResult(
                outcome=SkillOutcome.RECOVERABLE_FAILURE,
                detail=f"invalid_arguments: {exc.error_count()} validation error(s)",
            )

        try:
            for hook in self.hooks:
                hook.before(plugin, invocation, arguments)

            pending = plugin.handler(arguments, invocation.context)
            result = await pending if inspect.isawaitable(pending) else pending

            if result.outcome is SkillOutcome.SUCCESS:
                try:
                    data = plugin.output_model.model_validate(result.data)
                except ValidationError as exc:
                    result = result.model_copy(
                        update={
                            "outcome": SkillOutcome.RECOVERABLE_FAILURE,
                            "data": None,
                            "detail": (
                                f"invalid_skill_result: {exc.error_count()} validation error(s)"
                            ),
                        }
                    )
                else:
                    result = result.model_copy(update={"data": data.model_dump(mode="json")})

            for hook in self.hooks:
                result = hook.after(plugin, invocation, result)
            return result
        except SkillPolicyViolation as exc:
            return SkillResult(outcome=SkillOutcome.POLICY_DENIED, detail=exc.detail)
        except Exception as exc:  # noqa: BLE001 - plugin failures become bounded run errors
            return SkillResult(
                outcome=SkillOutcome.RECOVERABLE_FAILURE,
                detail="Skill execution failed; inspect the canonical run error.",
                errors=[
                    RunError(
                        kind=type(exc).__name__,
                        message="Skill plugin raised an unexpected exception.",
                    )
                ],
            )


__all__ = [
    "ActionableReviewPolicyHook",
    "ProvenancePolicyHook",
    "SafetyPolicyHook",
    "SkillExecutor",
    "SkillPolicyViolation",
]
