"""CellXP top-level LangGraph supervisor (roadmap N3)."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any, cast

from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt

from cellxp.agent.nodes import (
    critic,
    entity_resolver,
    evidence_integrator,
    input_normalizer,
    intent_classifier,
    planner,
    report_generator,
    risk_classifier,
    task_selector,
)
from cellxp.agent.routing import route_after_entities, route_after_risk, route_task
from cellxp.agent.state import (
    AgentState,
    Clarification,
    ClarificationAnswer,
    ExecutionCursor,
    NormalizedInputs,
    RunError,
    Step,
    Subtask,
)
from cellxp.domain.clock import utc_now_iso
from cellxp.domain.enums import IntentType, RunStatus, TaskStatus

Node = Callable[[AgentState], dict[str, object]]
CAPABILITY_NODES = (
    "variant_effect_subgraph",
    "gwas_subgraph",
    "crispr_subgraph",
    "annotation_subgraph",
    "binding_subgraph",
    "structure_subgraph",
    "origami_subgraph",
    "rag_subgraph",
    "visualization_subgraph",
)


def _apply_clarification(state: AgentState, raw_answer: Any) -> dict[str, object]:
    questions = [
        Clarification.model_validate(item).model_copy(deep=True)
        for item in state.get("clarifications", [])
    ]
    question = next((item for item in questions if item.blocking and item.answer is None), None)
    if question is None:
        return {"status": RunStatus.RUNNING}

    if isinstance(raw_answer, str):
        answer = ClarificationAnswer(freeform=raw_answer, answered_at=utc_now_iso())
    else:
        answer = ClarificationAnswer.model_validate(raw_answer)
        answer.answered_at = answer.answered_at or utc_now_iso()
    question.answer = answer

    selected_values = [
        option.value
        for option in question.options
        if option.id in answer.selected_option_ids and option.value is not None
    ]
    if answer.freeform is not None:
        selected_values.append(answer.freeform)

    update: dict[str, object] = {"clarifications": [question], "status": RunStatus.RUNNING}
    for value in selected_values:
        try:
            update["intent"] = IntentType(value)
            continue
        except ValueError:
            pass
        if "|" in value:
            organism, assembly = value.split("|", maxsplit=1)
            normalized = NormalizedInputs.model_validate(
                state.get("normalized_inputs", {})
            ).model_copy(deep=True)
            normalized.organism = organism.strip()
            normalized.assembly = assembly.strip()
            update["normalized_inputs"] = normalized
            continue
        context_organism, context_assembly = entity_resolver._context_from_query(value)
        if context_organism:
            normalized = NormalizedInputs.model_validate(
                state.get("normalized_inputs", {})
            ).model_copy(deep=True)
            normalized.organism = context_organism
            normalized.assembly = context_assembly
            update["normalized_inputs"] = normalized
    return update


def await_input(state: AgentState) -> dict[str, object]:
    questions = [Clarification.model_validate(item) for item in state.get("clarifications", [])]
    question = next(item for item in questions if item.blocking and item.answer is None)
    answer = interrupt(question.model_dump(mode="json"))
    return _apply_clarification(state, answer)


def _unimplemented_capability(state: AgentState) -> dict[str, object]:
    """Honest N3 boundary: exercise the loop without pretending later roadmap slices exist."""
    cursor = ExecutionCursor.model_validate(state.get("cursor", {}))
    subtasks = [
        Subtask.model_validate(item).model_copy(deep=True) for item in state.get("subtasks", [])
    ]
    active = next(item for item in subtasks if item.id == cursor.active_subtask_id)
    active.status = TaskStatus.FAILED
    message = f"Capability '{active.capability}' is not implemented in roadmap phase N3."
    return {
        "subtasks": subtasks,
        "steps": [
            Step(
                subtask_id=active.id,
                name=f"dispatch_{active.capability}",
                status=TaskStatus.FAILED,
                error=message,
                finished_at=utc_now_iso(),
            )
        ],
        "errors": [RunError(subtask_id=active.id, kind="CapabilityUnavailable", message=message)],
    }


def build_graph(
    *,
    capability_nodes: Mapping[str, Node] | None = None,
    checkpointer: Any | None = None,
):
    """Build the supervisor; tests/services may inject capability subgraphs and a checkpointer."""
    graph = StateGraph(AgentState)
    graph.add_node("input_normalizer", input_normalizer.run)
    graph.add_node("intent_classifier", intent_classifier.run)
    graph.add_node("risk_classifier", risk_classifier.run)
    graph.add_node("entity_resolver", entity_resolver.run)
    graph.add_node("await_input", await_input)
    graph.add_node("planner", planner.run)
    graph.add_node("task_selector", task_selector.run)
    graph.add_node("evidence_integrator", evidence_integrator.run)
    graph.add_node("critic", critic.run)
    graph.add_node("report_generator", report_generator.run)

    provided = capability_nodes or {}
    for name in CAPABILITY_NODES:
        # LangGraph's overloads cannot infer a callable selected from a runtime registry,
        # although each injected node has the same AgentState contract.
        graph.add_node(name, cast(Any, provided.get(name, _unimplemented_capability)))

    graph.add_edge(START, "input_normalizer")
    graph.add_edge("input_normalizer", "intent_classifier")
    graph.add_edge("intent_classifier", "risk_classifier")
    graph.add_conditional_edges(
        "risk_classifier",
        route_after_risk,
        {"entity_resolver": "entity_resolver", "report_generator": "report_generator"},
    )
    graph.add_conditional_edges(
        "entity_resolver",
        route_after_entities,
        {"await_input": "await_input", "planner": "planner"},
    )
    graph.add_edge("await_input", "planner")
    graph.add_edge("planner", "task_selector")
    graph.add_conditional_edges(
        "task_selector",
        route_task,
        {**{name: name for name in CAPABILITY_NODES}, "critic": "critic"},
    )
    for name in CAPABILITY_NODES:
        graph.add_edge(name, "evidence_integrator")
    graph.add_edge("evidence_integrator", "task_selector")
    graph.add_edge("critic", "report_generator")
    graph.add_edge("report_generator", END)
    return graph.compile(checkpointer=checkpointer)


app = build_graph()
