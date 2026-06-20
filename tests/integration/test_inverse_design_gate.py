"""X7 actionable inverse-design output is structurally review-gated (TST-4)."""

from langgraph.checkpoint.memory import InMemorySaver

from cellxp.agent.graph import build_graph
from cellxp.agent.state import Subtask
from cellxp.domain.artifacts import ArtifactRef
from cellxp.domain.enums import ArtifactType, RunStatus, TaskStatus


def _candidate_node(state):
    subtasks = [Subtask.model_validate(item).model_copy(deep=True) for item in state["subtasks"]]
    active = next(item for item in subtasks if item.id == state["cursor"].active_subtask_id)
    active.status = TaskStatus.DONE
    return {
        "subtasks": subtasks,
        "artifacts": [ArtifactRef(
            id="inverse-candidates", type=ArtifactType.GUIDE_TABLE,
            title="Candidate edits", subtask_id=active.id, actionable=True,
        )],
    }


def test_inverse_design_pauses_before_report():
    graph = build_graph(
        capability_nodes={"inverse_design_subgraph": _candidate_node},
        checkpointer=InMemorySaver(),
    )
    paused = graph.invoke(
        {
            "user_query": "Use inverse design for a desired effect at PCSK9 in human GRCh38",
            "target_effect": {"readout": "expression:PCSK9:liver", "direction": "decrease"},
        },
        {"configurable": {"thread_id": "inverse-review"}},
    )
    assert paused["status"] is RunStatus.AWAITING_REVIEW
    assert paused["__interrupt__"]
    assert "final_report" not in paused
