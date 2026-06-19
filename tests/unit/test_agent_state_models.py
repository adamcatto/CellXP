"""Agent state substructure model tests (Wave 0, state_schema.md §5-§15)."""

from cellxp.agent.state import (
    Budget,
    Clarification,
    ClarificationOption,
    Entity,
    Message,
    NormalizedInputs,
    Plan,
    Report,
    ReviewItem,
    ReviewState,
    RunError,
    Step,
    Subtask,
)
from cellxp.domain.enums import (
    ConfidenceBand,
    PlanKind,
    ReviewDecision,
    ReviewGateStatus,
    SequenceAlphabet,
    SubtaskType,
    TaskStatus,
)
from cellxp.domain.evidence import Confidence
from cellxp.domain.models import Variant
from cellxp.domain.sequences import BiologicalSequence


def test_message_defaults():
    m = Message(role="assistant", content="hi")
    assert m.id and m.created_at.endswith("+00:00")
    assert m.artifact_ids == [] and m.evidence_ids == []


def test_subtask_defaults_to_pending_nonactionable():
    s = Subtask(type=SubtaskType.VARIANT_EFFECT, capability="FR-13")
    assert s.status is TaskStatus.PENDING
    assert s.is_actionable is False
    assert s.depends_on == []


def test_plan_kind_enum():
    p = Plan(kind=PlanKind.COMPOSED, created_by="planner")
    assert p.revision == 0


def test_review_state_defaults_not_required():
    r = ReviewState()
    assert r.required is False
    assert r.status is ReviewGateStatus.NOT_REQUIRED
    item = ReviewItem(subject_ref="artifact:1", reason="actionable CRISPR guide")
    assert item.decision is ReviewDecision.PENDING


def test_normalized_inputs_holds_domain_types():
    ni = NormalizedInputs(
        organism="human",
        assembly="GRCh38",
        variants=[Variant(chrom="chr1", pos=99, ref="A", alt="T")],
        sequences=[BiologicalSequence(seq="ACGT", alphabet=SequenceAlphabet.DNA)],
    )
    assert ni.variants[0].pos == 99
    assert ni.sequences[0].alphabet is SequenceAlphabet.DNA


def test_entity_defaults_unresolved():
    e = Entity(type="variant", label="rs334")
    assert e.resolved is False
    assert e.refs == {} and e.ambiguity == []


def test_clarification_option_recommended():
    c = Clarification(
        question="Which assembly?",
        options=[
            ClarificationOption(label="GRCh38", value="GRCh38", is_recommended=True),
            ClarificationOption(label="GRCh37", value="GRCh37"),
        ],
    )
    assert c.blocking is True and c.allow_freeform is True
    assert c.options[0].is_recommended is True


def test_report_with_confidence_summary_roundtrips():
    r = Report(
        markdown="# result",
        citation_map={"[1]": "ev-1"},
        confidence_summary=Confidence(band=ConfidenceBand.MEDIUM, score=0.6),
    )
    assert Report.model_validate_json(r.model_dump_json()) == r


def test_step_and_error_and_budget_defaults():
    assert Step(name="call_alphagenome").status is TaskStatus.PENDING
    assert RunError(kind="CoordinateError", message="bad").recoverable is True
    assert Budget().spent == {}
