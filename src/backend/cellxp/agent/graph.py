from langgraph.graph import StateGraph, START, END
from cellxp.agent.state import AgentState
from cellxp.agent.routing import route_task


def _node(name):
    def inner(state: AgentState):
        return {"evidence": [{"node": name, "status": "stub"}]}
    return inner


def report_generator(state: AgentState):
    return {"final_report": "CellXP run completed."}


def build_graph():
    graph = StateGraph(AgentState)
    for name in [
        "input_normalizer", "intent_classifier", "entity_resolver", "risk_classifier", "planner",
        "variant_effect_subgraph", "gwas_subgraph", "crispr_subgraph", "annotation_subgraph",
        "binding_subgraph", "structure_subgraph", "origami_subgraph", "rag_subgraph",
        "visualization_subgraph", "evidence_integrator", "critic",
    ]:
        graph.add_node(name, _node(name))
    graph.add_node("task_selector", lambda state: state)
    graph.add_node("report_generator", report_generator)
    graph.add_edge(START, "input_normalizer")
    graph.add_edge("input_normalizer", "intent_classifier")
    graph.add_edge("intent_classifier", "entity_resolver")
    graph.add_edge("entity_resolver", "risk_classifier")
    graph.add_edge("risk_classifier", "planner")
    graph.add_edge("planner", "task_selector")
    graph.add_conditional_edges("task_selector", route_task, {
        "variant_effect_subgraph": "variant_effect_subgraph",
        "gwas_subgraph": "gwas_subgraph",
        "crispr_subgraph": "crispr_subgraph",
        "annotation_subgraph": "annotation_subgraph",
        "binding_subgraph": "binding_subgraph",
        "structure_subgraph": "structure_subgraph",
        "origami_subgraph": "origami_subgraph",
        "rag_subgraph": "rag_subgraph",
        "visualization_subgraph": "visualization_subgraph",
        "report_generator": "report_generator",
    })
    for name in ["variant_effect_subgraph", "gwas_subgraph", "crispr_subgraph", "annotation_subgraph", "binding_subgraph", "structure_subgraph", "origami_subgraph", "rag_subgraph", "visualization_subgraph"]:
        graph.add_edge(name, "evidence_integrator")
    graph.add_edge("evidence_integrator", "critic")
    graph.add_edge("critic", "report_generator")
    graph.add_edge("report_generator", END)
    return graph.compile()

app = build_graph()
