"""AgentState TypedDict + reducer tests (Wave 0, state_schema.md §4, §16)."""

from operator import add
from typing import get_type_hints

from cellxp.agent.state import (
    AgentState,
    Clarification,
    Entity,
    merge_by_id,
)


def test_agent_state_is_typeddict_with_target_keys():
    keys = set(AgentState.__annotations__)
    assert {"messages", "evidence", "artifacts", "steps", "errors"} <= keys  # append fields
    assert {"entities", "clarifications"} <= keys  # merge-by-id fields
    assert {"plan", "subtasks", "cursor", "review", "status", "intent", "risk",
            "normalized_inputs", "final_report", "budget"} <= keys  # last-write-wins


def test_merge_by_id_replaces_same_id_and_appends_new():
    e1 = Entity(id="x", type="gene", label="TP53", resolved=False)
    e1b = Entity(id="x", type="gene", label="TP53", resolved=True)  # update
    e2 = Entity(id="y", type="variant", label="rs334")
    merged = merge_by_id([e1], [e1b, e2])
    assert len(merged) == 2
    assert merged[0].resolved is True  # replaced in place
    assert merged[1].id == "y"  # appended


def test_merge_by_id_empty_sides():
    e = Clarification(id="c", question="?")
    assert merge_by_id([], [e]) == [e]
    assert merge_by_id([e], []) == [e]


def test_append_and_merge_reducers_are_attached():
    hints = get_type_hints(AgentState, include_extras=True)
    # Append fields carry operator.add as their Annotated reducer metadata.
    for field in ("evidence", "steps", "messages", "artifacts", "errors"):
        assert hints[field].__metadata__ == (add,)
    # Merge-by-id fields carry the merge_by_id reducer.
    for field in ("entities", "clarifications"):
        assert hints[field].__metadata__ == (merge_by_id,)
    # Last-write-wins fields are plain (no Annotated metadata).
    assert not hasattr(hints["plan"], "__metadata__")


def test_graph_still_compiles_and_runs_smoke():
    # Upgrading the state must not break the existing scaffold graph.
    from cellxp.agent.graph import app

    out = app.invoke({"user_query": "smoke", "subtasks": [{"type": "report"}]})
    assert "final_report" in out
