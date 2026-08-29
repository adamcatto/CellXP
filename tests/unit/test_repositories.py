"""Repository round-trip + append-only tests (Wave 0, RS-2/RS-3, PROV-2/PROV-3)."""

import pytest
from cellxp.agent.state import (
    AgentState,
    Budget,
    Clarification,
    ClarificationOption,
    Message,
    Plan,
    Report,
    ReviewItem,
    ReviewState,
    RunError,
    Step,
    Subtask,
)
from cellxp.domain.artifacts import ArtifactRef
from cellxp.domain.clock import utc_now_iso
from cellxp.domain.enums import (
    ArtifactType,
    IntentType,
    PlanKind,
    ReviewDecision,
    RunStatus,
    SourceKind,
    SubtaskType,
    TaskStatus,
)
from cellxp.domain.evidence import Confidence, EvidenceItem, Provenance
from cellxp.domain.ids import new_id
from cellxp.domain.safety import RiskAssessment
from cellxp.storage.database import make_session_factory, session_scope
from cellxp.storage.models import Base
from cellxp.storage.models import Step as StepRow
from cellxp.storage.models import Subtask as SubtaskRow
from cellxp.storage.repositories import AppendOnlyError, StateRepository


@pytest.fixture
def factory():
    f = make_session_factory("sqlite://")
    Base.metadata.create_all(f.kw["bind"])
    return f


# IDs are uuid columns (`relational_schema.md` §3), so use real ids and reference them.
IDS = {k: new_id() for k in ("run", "sub", "step", "ev", "art", "msg", "clar", "rev", "err")}


def _full_state() -> AgentState:
    ev = EvidenceItem(
        id=IDS["ev"], source="AlphaGenome", source_kind=SourceKind.MODEL,
        claim="predicted enhancer disruption", value={"delta": 0.42},
        confidence=Confidence(band="high", score=0.9, basis="model applicability"),
        provenance=Provenance(tool="alphagenome", tool_version="r3", input_hash="abc"),
        subtask_id=IDS["sub"], step_id=IDS["step"],
    )
    art = ArtifactRef(
        id=IDS["art"], type=ArtifactType.GUIDE_TABLE, title="Guide table", subtask_id=IDS["sub"],
        storage_ref="cas/deadbeef", summary={"rows": 5}, evidence_ids=[IDS["ev"]], actionable=True,
    )
    return {
        "run_id": IDS["run"],
        "schema_version": "1",
        "created_at": utc_now_iso(),
        "status": RunStatus.COMPLETED,
        "intent": IntentType.VARIANT_EFFECT,
        "risk": RiskAssessment(decision="allow", rationale="benign query"),
        "plan": Plan(kind=PlanKind.ATOMIC, created_by="router", rationale="single capability"),
        "budget": Budget(max_tokens=1000, spent={"tokens": 12.0}),
        "normalized_inputs": None,
        "final_report": Report(markdown="## Result", limitations=["preliminary"]),
        "messages": [
            Message(id=IDS["msg"], role="user", content="interpret rs334",
                    created_at=utc_now_iso()),
        ],
        "subtasks": [
            Subtask(id=IDS["sub"], type=SubtaskType.VARIANT_EFFECT, capability="FR-12",
                    inputs={"rsid": "rs334"}, status=TaskStatus.DONE, is_actionable=True),
        ],
        "steps": [
            Step(id=IDS["step"], subtask_id=IDS["sub"], name="call_alphagenome",
                 tool="alphagenome", tool_version="r3", status=TaskStatus.DONE,
                 started_at=utc_now_iso()),
        ],
        "evidence": [ev],
        "artifacts": [art],
        "clarifications": [
            Clarification(id=IDS["clar"], question="Which assembly?",
                          options=[ClarificationOption(id=new_id(), label="GRCh38")]),
        ],
        "review": ReviewState(
            required=True,
            items=[ReviewItem(id=IDS["rev"], subject_ref=IDS["art"],
                              reason="actionable guide table", risks=["off-target"],
                              evidence_ids=[IDS["ev"]], decision=ReviewDecision.PENDING)],
        ),
        "errors": [
            RunError(id=IDS["err"], kind="Timeout", message="slow upstream", recoverable=True,
                     at=utc_now_iso()),
        ],
    }


def test_state_roundtrips_through_postgres_schema(factory):
    state = _full_state()
    with session_scope(factory) as s:
        StateRepository(s).save(state, session_id=None)

    with session_scope(factory) as s:
        loaded = StateRepository(s).load(IDS["run"])

    # Run-level scalars
    assert loaded["run_id"] == IDS["run"]
    assert loaded["status"] is RunStatus.COMPLETED
    assert loaded["intent"] is IntentType.VARIANT_EFFECT
    assert loaded["created_at"] == state["created_at"]
    assert loaded["risk"] == state["risk"]
    assert loaded["plan"] == state["plan"]
    assert loaded["budget"] == state["budget"]
    assert loaded["final_report"] == state["final_report"]

    # Children (RS-3 equivalence)
    assert loaded["messages"] == state["messages"]
    assert loaded["subtasks"] == state["subtasks"]
    assert loaded["steps"] == state["steps"]
    assert loaded["evidence"] == state["evidence"]
    assert loaded["clarifications"] == state["clarifications"]
    assert loaded["errors"] == state["errors"]

    # Artifact + its evidence link (PROV-2)
    assert loaded["artifacts"][0].evidence_ids == [IDS["ev"]]
    assert loaded["artifacts"][0] == state["artifacts"][0]

    # Review items round-trip
    assert loaded["review"].items == state["review"].items


def test_minimal_state_roundtrips(factory):
    with session_scope(factory) as s:
        rid = new_id()
        StateRepository(s).save({"run_id": rid})
    with session_scope(factory) as s:
        loaded = StateRepository(s).load(rid)
    assert loaded["run_id"] == rid
    assert loaded["status"] is RunStatus.QUEUED
    assert loaded["messages"] == []


def test_load_unknown_run_raises(factory):
    with session_scope(factory) as s, pytest.raises(KeyError):
        StateRepository(s).load(new_id())


def test_delete_append_only_row_refused(factory):
    with session_scope(factory) as s:
        StateRepository(s).save(_full_state())
    with session_scope(factory) as s:
        repo = StateRepository(s)
        step = s.get(StepRow, IDS["step"])
        with pytest.raises(AppendOnlyError, match="append-only"):  # RS-2
            repo.delete(step)


def test_update_append_only_row_refused(factory):
    with session_scope(factory) as s:
        StateRepository(s).save(_full_state())
    with session_scope(factory) as s:
        repo = StateRepository(s)
        step = s.get(StepRow, IDS["step"])
        with pytest.raises(AppendOnlyError):  # PROV-3
            repo.update(step, name="mutated")


def test_mutable_row_can_be_updated_and_deleted(factory):
    # subtasks is NOT append-only — repository allows it.
    with session_scope(factory) as s:
        StateRepository(s).save(_full_state())
    with session_scope(factory) as s:
        repo = StateRepository(s)
        sub = s.get(SubtaskRow, IDS["sub"])
        repo.update(sub, status=TaskStatus.SKIPPED)
        assert sub.status is TaskStatus.SKIPPED
        repo.delete(sub)
