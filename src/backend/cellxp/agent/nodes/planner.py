"""Typed atomic/composed plan construction for the N3 orchestration spine (FR-5)."""

from __future__ import annotations

from cellxp.agent.nodes.intent_classifier import classify_intents
from cellxp.agent.state import AgentState, ExecutionCursor, NormalizedInputs, Plan, Subtask
from cellxp.domain.enums import IntentType, PlanKind, RunStatus, SubtaskType

_CAPABILITY_BY_INTENT: dict[IntentType, SubtaskType] = {
    IntentType.VARIANT_EFFECT: SubtaskType.VARIANT_EFFECT,
    IntentType.GWAS_QTL: SubtaskType.GWAS,
    IntentType.CRISPR_DESIGN: SubtaskType.CRISPR,
    IntentType.ANNOTATION: SubtaskType.ANNOTATION,
    IntentType.BINDING: SubtaskType.BINDING,
    IntentType.STRUCTURE: SubtaskType.STRUCTURE,
    IntentType.ORIGAMI: SubtaskType.ORIGAMI,
    IntentType.LITERATURE: SubtaskType.RAG,
    IntentType.VISUALIZATION: SubtaskType.VISUALIZATION,
}


def _deduplicate(items: list[IntentType]) -> list[IntentType]:
    return list(dict.fromkeys(items))


def run(state: AgentState) -> dict[str, object]:
    intents = _deduplicate(classify_intents(state))
    primary = IntentType(state.get("intent", intents[0]))
    if primary not in intents and primary not in {IntentType.AMBIGUOUS, IntentType.OUT_OF_DOMAIN}:
        intents.insert(0, primary)

    normalized = NormalizedInputs.model_validate(state.get("normalized_inputs", {}))
    shared_inputs = normalized.model_dump(mode="json")
    subtasks: list[Subtask] = []

    composed_evidence = {
        IntentType.VARIANT_EFFECT,
        IntentType.GWAS_QTL,
        IntentType.STRUCTURE,
    }.issubset(intents)

    if composed_evidence:
        effect = Subtask(
            type=SubtaskType.VARIANT_EFFECT,
            capability=SubtaskType.VARIANT_EFFECT.value,
            inputs=shared_inputs,
        )
        gwas = Subtask(
            type=SubtaskType.GWAS,
            capability=SubtaskType.GWAS.value,
            inputs=shared_inputs,
            depends_on=[effect.id],
        )
        structure = Subtask(
            type=SubtaskType.STRUCTURE,
            capability=SubtaskType.STRUCTURE.value,
            inputs={**shared_inputs, "source": "variant_effect", "kind": "protein"},
            depends_on=[gwas.id],
        )
        subtasks = [effect, gwas, structure]
    elif primary is IntentType.INVERSE_EDIT_DESIGN:
        effect = Subtask(
            type=SubtaskType.VARIANT_EFFECT,
            capability=SubtaskType.VARIANT_EFFECT.value,
            inputs=shared_inputs,
        )
        edit = Subtask(
            type=SubtaskType.CRISPR,
            capability=SubtaskType.CRISPR.value,
            inputs=shared_inputs,
            depends_on=[effect.id],
            is_actionable=True,
        )
        subtasks = [effect, edit]
    elif primary is IntentType.SYSTEMS_ANALYSIS:
        annotation = Subtask(
            type=SubtaskType.ANNOTATION,
            capability=SubtaskType.ANNOTATION.value,
            inputs=shared_inputs,
        )
        literature = Subtask(
            type=SubtaskType.RAG,
            capability=SubtaskType.RAG.value,
            inputs=shared_inputs,
            depends_on=[annotation.id],
        )
        subtasks = [annotation, literature]
    else:
        for intent in intents:
            capability = _CAPABILITY_BY_INTENT.get(intent)
            if capability is not None:
                subtasks.append(
                    Subtask(
                        type=capability,
                        capability=capability.value,
                        inputs=shared_inputs,
                        is_actionable=capability in {SubtaskType.CRISPR, SubtaskType.ORIGAMI},
                    )
                )

    old_plan = state.get("plan")
    revision = Plan.model_validate(old_plan).revision + 1 if old_plan else 0
    kind = PlanKind.ATOMIC if len(subtasks) == 1 else PlanKind.COMPOSED
    plan = Plan(
        kind=kind,
        created_by="planner",
        revision=revision,
        rationale=(
            "One capability satisfies the request."
            if kind is PlanKind.ATOMIC
            else "The request requires an ordered multi-capability plan."
        ),
    )
    return {
        "plan": plan,
        "subtasks": subtasks,
        "cursor": ExecutionCursor(remaining=[subtask.id for subtask in subtasks]),
        "status": RunStatus.RUNNING,
    }
