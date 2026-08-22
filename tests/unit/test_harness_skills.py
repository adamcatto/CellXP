from __future__ import annotations

import asyncio

from pydantic import BaseModel

from cellxp.agent.state import Step, Subtask
from cellxp.domain.artifacts import ArtifactRef
from cellxp.domain.enums import ArtifactType, RiskDecision, SubtaskType, TaskStatus
from cellxp.domain.safety import RiskAssessment
from cellxp.harness import (
    SkillContext,
    SkillExecutor,
    SkillInvocation,
    SkillKind,
    SkillOutcome,
    SkillPlugin,
    SkillRegistry,
    SkillRelease,
    SkillResult,
    SkillSideEffect,
    SkillSpec,
)
from cellxp.harness.langgraph_compat import CapabilitySkillInput, legacy_capability_plugin


class _Input(BaseModel):
    value: int


def _plugin(
    handler,
    *,
    name: str = "cellxp.test",
    side_effect: SkillSideEffect = SkillSideEffect.READ,
) -> SkillPlugin:
    return SkillPlugin(
        spec=SkillSpec(
            name=name,
            version="1.0.0",
            description="A test skill.",
            kind=SkillKind.CAPABILITY,
            side_effect=side_effect,
            implementation="test",
        ),
        input_model=_Input,
        handler=handler,
    )


def _context(decision: RiskDecision | None = RiskDecision.ALLOW) -> SkillContext:
    risk = RiskAssessment(decision=decision) if decision is not None else None
    return SkillContext(session_id="session-1", run_id="run-1", risk=risk)


def _invoke(executor: SkillExecutor, **kwargs) -> SkillResult:
    invocation = SkillInvocation(
        skill_name=kwargs.pop("skill_name", "cellxp.test"),
        arguments=kwargs.pop("arguments", {"value": 1}),
        context=kwargs.pop("context", _context()),
        **kwargs,
    )
    return asyncio.run(executor.invoke(invocation))


def test_registry_is_append_only_and_projects_bounded_tool_schema() -> None:
    plugin = _plugin(
        lambda arguments, context: SkillResult(
            steps=[Step(name="test", status=TaskStatus.DONE)]
        )
    )
    registry = SkillRegistry()
    registry.register(plugin)

    try:
        registry.register(plugin)
    except ValueError as exc:
        assert "already registered" in str(exc)
    else:
        raise AssertionError("duplicate skill registration must fail")

    definition = registry.tool_definitions()[0]
    assert definition["name"] == "cellxp.test"
    assert definition["inputSchema"]["properties"] == {
        "value": {"title": "Value", "type": "integer"}
    }
    assert "AgentState" not in str(definition)


def test_invalid_arguments_and_missing_risk_fail_before_handler() -> None:
    calls = 0

    def handler(arguments, context):
        nonlocal calls
        calls += 1
        return SkillResult(steps=[Step(name="test", status=TaskStatus.DONE)])

    registry = SkillRegistry()
    registry.register(_plugin(handler))
    executor = SkillExecutor(registry)

    invalid = _invoke(executor, arguments={"value": "not-an-int"})
    missing_risk = _invoke(executor, context=_context(None))
    blocked = _invoke(executor, context=_context(RiskDecision.BLOCK))

    assert invalid.outcome is SkillOutcome.RECOVERABLE_FAILURE
    assert missing_risk.outcome is SkillOutcome.POLICY_DENIED
    assert blocked.outcome is SkillOutcome.POLICY_DENIED
    assert calls == 0


def test_actionable_result_is_withheld_until_canonical_approval() -> None:
    artifact = ArtifactRef(
        id="guide-pool-1",
        type=ArtifactType.GUIDE_TABLE,
        title="Candidate guides",
        actionable=True,
    )
    registry = SkillRegistry()
    registry.register(
        _plugin(
            lambda arguments, context: SkillResult(
                steps=[Step(name="design", status=TaskStatus.DONE)],
                artifacts=[artifact],
            ),
            side_effect=SkillSideEffect.ACTIONABLE,
        )
    )
    executor = SkillExecutor(registry)

    pending = _invoke(executor)
    approved_context = _context()
    approved_context.approved_subject_ids.add("guide-pool-1")
    approved = _invoke(executor, context=approved_context)

    assert pending.release is SkillRelease.AWAITING_REVIEW
    assert pending.review_subject_ids == ["guide-pool-1"]
    assert approved.release is SkillRelease.RELEASABLE


def test_legacy_capability_wrapper_constructs_only_bounded_state() -> None:
    seen: dict[str, object] = {}

    def node(state):
        seen.update(state)
        return {
            "subtasks": state["subtasks"],
            "steps": [Step(name="legacy_call", status=TaskStatus.DONE)],
        }

    plugin = legacy_capability_plugin(name="structure", node=node)
    registry = SkillRegistry()
    registry.register(plugin)
    executor = SkillExecutor(registry)
    request = CapabilitySkillInput(
        normalized_inputs={},
        subtask=Subtask(type=SubtaskType.STRUCTURE, capability="structure"),
        query_summary="Predict a protein structure.",
    )
    result = _invoke(
        executor,
        skill_name="cellxp.structure",
        arguments=request.model_dump(mode="json"),
    )

    assert result.outcome is SkillOutcome.SUCCESS
    assert result.steps[0].name == "legacy_call"
    assert seen["run_id"] == "run-1"
    assert "messages" not in seen
    assert "raw_inputs" not in seen
    assert "final_report" not in seen
