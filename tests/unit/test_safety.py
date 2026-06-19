"""Safety risk-assessment contract tests (Wave 0)."""

from cellxp.domain.enums import RiskDecision
from cellxp.domain.safety import RiskAssessment


def test_allow_proceeds_without_forced_review():
    r = RiskAssessment(decision=RiskDecision.ALLOW)
    assert r.allows_capabilities is True
    assert r.is_blocked is False
    assert r.forces_review_gate is False


def test_restrict_forces_review_gate_but_proceeds():
    r = RiskAssessment(decision=RiskDecision.RESTRICT, rationale="dual-use, legitimate intent")
    assert r.allows_capabilities is True
    assert r.forces_review_gate is True
    assert r.is_blocked is False


def test_block_forbids_capability_work():
    r = RiskAssessment(
        decision=RiskDecision.BLOCK,
        rationale="primary purpose hazardous",
        hazard_signals=["select_agent"],
        escalate=True,
    )
    assert r.is_blocked is True
    assert r.allows_capabilities is False
    assert r.hazard_signals == ["select_agent"]


def test_roundtrips_json():
    r = RiskAssessment(decision=RiskDecision.RESTRICT, hazard_signals=["x"])
    assert RiskAssessment.model_validate_json(r.model_dump_json()) == r
