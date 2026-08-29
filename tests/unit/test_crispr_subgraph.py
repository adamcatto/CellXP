"""X5 CRISPR subgraph tests."""

from cellxp.agent.state import AgentState, ExecutionCursor, NormalizedInputs, Subtask
from cellxp.agent.subgraphs.crispr import build_subgraph
from cellxp.domain.enums import ConfidenceBand, SubtaskType, TaskStatus
from cellxp.domain.evidence import Confidence, Provenance
from cellxp.domain.models import GenomicInterval
from cellxp.services.crispr import (
    CrisprResult,
    CrisprService,
    EditOutcomeResult,
    Guide,
    GuideScoringResult,
    OffTargetResult,
)


class Backend:
    def design_guides(self, request):
        return CrisprResult(guides=[Guide(
            spacer="ACGTACGTACGTACGTACGT", pam="NGG", strand="+", cut_site=112,
            on_target_score=.8, specificity_score=.9,
            confidence=Confidence(band=ConfidenceBand.HIGH),
            provenance=Provenance(tool="test", tool_version="1"),
        )], editing_system="SpCas9", rationale="test", storage_ref="obj://guides")
    def enumerate_off_targets(self, request): return OffTargetResult()
    def score_on_target(self, request): return GuideScoringResult(scores={})
    def predict_edit_outcomes(self, request): return EditOutcomeResult(efficiencies={}, outcome_model="x")


def state(inputs=None):
    subtask = Subtask(type=SubtaskType.CRISPR, capability="crispr", status=TaskStatus.RUNNING,
                      is_actionable=True)
    normalized = inputs or NormalizedInputs(
        organism="Homo sapiens", assembly="GRCh38",
        intervals=[GenomicInterval(chrom="chr1", start=100, end=200)],
    )
    return AgentState(subtasks=[subtask], cursor=ExecutionCursor(active_subtask_id=subtask.id),
                      normalized_inputs=normalized)


def test_subgraph_completes_and_preserves_actionability():
    result = build_subgraph(crispr_service=CrisprService(backend=Backend()))(state())
    assert Subtask.model_validate(result["subtasks"][0]).status is TaskStatus.DONE
    assert result["artifacts"][0].actionable is True
    assert result["evidence"][0].subtask_id == result["subtasks"][0].id


def test_subgraph_fails_without_target():
    result = build_subgraph()(state(NormalizedInputs(organism="Homo sapiens", assembly="GRCh38")))
    assert Subtask.model_validate(result["subtasks"][0]).status is TaskStatus.FAILED
    assert result["errors"]


def test_no_backend_is_valid_candidate_empty_path():
    result = build_subgraph()(state())
    assert Subtask.model_validate(result["subtasks"][0]).status is TaskStatus.DONE
