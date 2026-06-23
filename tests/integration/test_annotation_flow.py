"""Supervisor integration for the annotation capability subgraph (L1, FR-16)."""

from cellxp.agent.graph import build_graph, production_capability_nodes
from cellxp.domain.enums import RunStatus


def test_supervisor_dispatches_annotation_without_n3_scaffold_error() -> None:
    graph = build_graph(capability_nodes=production_capability_nodes())

    result = graph.invoke(
        {
            "user_query": "/annotate chr1:1000-2000",
            "normalized_inputs": {
                "organism": "Homo sapiens",
                "assembly": "GRCh38",
            },
        }
    )

    assert result["status"] is RunStatus.COMPLETED
    assert result["final_report"].markdown
    step_names = {step.name for step in result["steps"]}
    assert "classify_scope" in step_names
    assert "call_annotation" in step_names
    assert not any(error.kind == "CapabilityUnavailable" for error in result.get("errors", []))
