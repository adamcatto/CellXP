"""N3/X1 integration through the supervisor and real GWAS subgraph."""

from cellxp.agent.graph import build_graph
from cellxp.agent.subgraphs.gwas import build_subgraph
from cellxp.domain.enums import RunStatus


def test_supervisor_dispatches_gwas_subgraph_with_trace() -> None:
    graph = build_graph(capability_nodes={"gwas_subgraph": build_subgraph()})

    result = graph.invoke(
        {"user_query": "Summarize human GRCh38 GWAS evidence at chr1:1000-1100"}
    )

    assert result["status"] is RunStatus.COMPLETED
    assert result["final_report"].markdown
    step_names = {step.name for step in result["steps"]}
    assert "resolve_gwas_subject" in step_names
    assert "query_gwas_evidence" in step_names
