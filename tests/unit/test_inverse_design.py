"""X7 inverse-design service and routing tests (FR-18c)."""

from cellxp.agent.nodes.planner import run as plan
from cellxp.agent.state import AgentState, ExecutionCursor, NormalizedInputs, Plan, Subtask
from cellxp.agent.subgraphs.inverse_design import build_subgraph
from cellxp.domain.enums import ConfidenceBand, PlanKind, SubtaskType, TaskStatus
from cellxp.domain.evidence import Confidence, Provenance
from cellxp.domain.models import GenomicInterval
from cellxp.services.base import ServiceOutcome
from cellxp.services.crispr import EditSpec
from cellxp.services.inverse_design import (
    CandidateAssessment, CandidateProposal, EffectTarget, InverseDesignRequest,
    InverseDesignService, SearchBudget,
)


class Backend:
    def propose(self, request, iteration):
        return [CandidateProposal(edit=EditSpec(position=100 + iteration, ref="A", alt="G"),
                                  editor="base_editor")]

    def assess(self, request, candidates):
        return [CandidateAssessment(
            predicted_effect=.75 - candidate.edit.position % 100 * .05,
            collateral_penalty=.1, feasibility=.8, off_target_penalty=.05,
            confidence=Confidence(band=ConfidenceBand.MEDIUM),
            provenance=Provenance(tool="forward_oracle+crispr", tool_version="test"),
        ) for candidate in candidates]


def request():
    return InverseDesignRequest(
        target_effect=EffectTarget(readout="expression:PCSK9:liver", direction="decrease", magnitude=.7),
        locus=GenomicInterval(chrom="chr1", start=100, end=200),
        organism="Homo sapiens", assembly="GRCh38", budget=SearchBudget(max_iterations=2),
    )


def test_service_runs_bounded_search_and_emits_actionable_pareto_candidates():
    result = InverseDesignService(backend=Backend()).design(request())
    assert result.outcome is ServiceOutcome.OK
    assert result.value and result.value.iterations == 2
    assert len(result.value.candidates) == 2
    assert any(item.pareto_front for item in result.value.candidates)
    assert result.artifacts[0].actionable is True
    assert len(result.evidence) == 2


def test_service_without_backend_is_unsupported():
    assert InverseDesignService().design(request()).outcome is ServiceOutcome.UNSUPPORTED


def test_planner_routes_inverse_intent_to_composed_actionable_oracle():
    result = plan(AgentState(
        user_query="Use inverse design for a desired effect at PCSK9",
        target_effect={"readout": "expression:PCSK9:liver", "direction": "decrease"},
        normalized_inputs=NormalizedInputs(organism="Homo sapiens", assembly="GRCh38",
                                           identifiers=["PCSK9"]),
    ))
    subtask = Subtask.model_validate(result["subtasks"][0])
    assert Plan.model_validate(result["plan"]).kind is PlanKind.COMPOSED
    assert subtask.type is SubtaskType.INVERSE_DESIGN
    assert subtask.is_actionable


def test_subgraph_preserves_actionability_and_provenance():
    subtask = Subtask(type=SubtaskType.INVERSE_DESIGN, capability="inverse_design",
                      status=TaskStatus.RUNNING, is_actionable=True,
                      inputs={"target_effect": request().target_effect.model_dump()})
    state = AgentState(
        subtasks=[subtask], cursor=ExecutionCursor(active_subtask_id=subtask.id),
        normalized_inputs=NormalizedInputs(
            organism="Homo sapiens", assembly="GRCh38",
            intervals=[GenomicInterval(chrom="chr1", start=100, end=200)],
        ),
    )
    result = build_subgraph(inverse_service=InverseDesignService(backend=Backend()))(state)
    assert Subtask.model_validate(result["subtasks"][0]).status is TaskStatus.DONE
    assert result["artifacts"][0].actionable
    assert all(item.subtask_id == subtask.id for item in result["evidence"])
