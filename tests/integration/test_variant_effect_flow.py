"""N3/N5 integration through the supervisor and real variant-effect subgraph."""

from cellxp.agent.graph import build_graph
from cellxp.agent.subgraphs.variant_effect import build_subgraph
from cellxp.domain.enums import RunStatus


def test_supervisor_dispatches_variant_subgraph_and_reports_honest_backend_gap() -> None:
    graph = build_graph(capability_nodes={"variant_effect_subgraph": build_subgraph()})

    result = graph.invoke(
        {"user_query": "Assess human GRCh38 variant chr1:1000 A>T for regulatory effect"}
    )

    assert result["status"] is RunStatus.COMPLETED
    assert result["final_report"].markdown
    step_names = {step.name for step in result["steps"]}
    assert "extract_variant_context" in step_names
    assert "call_effect_oracle" in step_names
    assert "produced no evidence" in result["final_report"].markdown
    assert result["final_report"].limitations
