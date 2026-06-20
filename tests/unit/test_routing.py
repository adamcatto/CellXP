"""Supervisor conditional routing regressions."""

from cellxp.agent.routing import route_after_entities
from cellxp.agent.state import AgentState, Clarification


def test_report_sentinel_bypasses_open_intent_clarification():
    state = AgentState(
        subtasks=[{"type": "report"}],
        clarifications=[Clarification(question="Which analysis?")],
    )
    assert route_after_entities(state) == "planner"
