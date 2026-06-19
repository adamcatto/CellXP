def route_task(state):
    task = (state.get("subtasks") or [{}])[0].get("type", "report")
    return {
        "variant_effect": "variant_effect_subgraph",
        "gwas": "gwas_subgraph",
        "crispr": "crispr_subgraph",
        "annotation": "annotation_subgraph",
        "binding": "binding_subgraph",
        "structure": "structure_subgraph",
        "origami": "origami_subgraph",
        "rag": "rag_subgraph",
        "visualization": "visualization_subgraph",
    }.get(task, "report_generator")
