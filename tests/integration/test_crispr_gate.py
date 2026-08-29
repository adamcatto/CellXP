"""X6 integration: actionable CRISPR output cannot bypass review (FR-25/26)."""

from cellxp.agent.graph import build_graph
from cellxp.agent.state import Subtask
from cellxp.domain.artifacts import ArtifactRef
from cellxp.domain.enums import ArtifactType, ReviewGateStatus, RunStatus, TaskStatus
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command


def _crispr_candidate(state):
    subtasks = [Subtask.model_validate(item).model_copy(deep=True) for item in state["subtasks"]]
    active = next(item for item in subtasks if item.id == state["cursor"].active_subtask_id)
    active.status = TaskStatus.DONE
    artifact = ArtifactRef(
        id="candidate-guides", type=ArtifactType.GUIDE_TABLE,
        title="Candidate guides", subtask_id=active.id, actionable=True,
    )
    return {"subtasks": subtasks, "artifacts": [artifact]}


def test_crispr_run_interrupts_before_report_and_resumes_after_approval():
    graph = build_graph(
        capability_nodes={"crispr_subgraph": _crispr_candidate},
        checkpointer=InMemorySaver(),
    )
    config = {"configurable": {"thread_id": "crispr-review"}}

    paused = graph.invoke(
        {"user_query": "Design CRISPR guides for PCSK9 in human GRCh38"}, config
    )

    assert paused["__interrupt__"]
    assert paused["status"] is RunStatus.AWAITING_REVIEW
    assert "final_report" not in paused
    payload = paused["__interrupt__"][0].value
    assert payload["status"] == "pending"
    item_id = payload["items"][0]["id"]

    completed = graph.invoke(Command(resume={item_id: "approved"}), config)
    assert completed["review"].status is ReviewGateStatus.APPROVED
    assert completed["status"] is RunStatus.COMPLETED
    assert completed["final_report"]
