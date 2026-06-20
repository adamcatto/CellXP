"""X4 composed-evidence planning tests."""

from cellxp.agent.nodes.planner import run
from cellxp.agent.state import AgentState, NormalizedInputs, Plan, Subtask
from cellxp.domain.enums import PlanKind, SubtaskType
from cellxp.domain.models import Variant


def test_variant_gwas_fold_is_an_ordered_composed_plan():
    state = AgentState(
        user_query="Assess this variant, check GWAS evidence, then fold the affected protein structure",
        normalized_inputs=NormalizedInputs(
            organism="Homo sapiens",
            assembly="GRCh38",
            variants=[Variant(chrom="chr1", pos=100, ref="A", alt="G")],
        ),
    )

    result = run(state)
    plan = Plan.model_validate(result["plan"])
    subtasks = [Subtask.model_validate(item) for item in result["subtasks"]]

    assert plan.kind is PlanKind.COMPOSED
    assert [item.type for item in subtasks] == [
        SubtaskType.VARIANT_EFFECT,
        SubtaskType.GWAS,
        SubtaskType.STRUCTURE,
    ]
    assert subtasks[1].depends_on == [subtasks[0].id]
    assert subtasks[2].depends_on == [subtasks[1].id]


def test_atomic_variant_plan_is_unchanged():
    result = run(
        AgentState(
            user_query="Assess this variant",
            normalized_inputs=NormalizedInputs(
                organism="Homo sapiens",
                assembly="GRCh38",
                variants=[Variant(chrom="chr1", pos=100, ref="A", alt="G")],
            ),
        )
    )
    assert Plan.model_validate(result["plan"]).kind is PlanKind.ATOMIC
