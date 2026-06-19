"""Safety risk assessment types.

The early risk gate (`risk_classifier`, `FR-34`) runs before any capability work and writes
a `RiskAssessment` to state (`state_schema.md` §4, `safety_model.md` §3). `block` refuses or
escalates; `restrict` proceeds but forces the human-review gate on actionable output and
enables extra audit logging; `allow` proceeds normally. Hazard recall must stay at 100% with
over-refusal low (`success_metrics.md` D5), so ambiguity resolves toward `block`, not `allow`.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from .enums import RiskDecision


class RiskAssessment(BaseModel):
    """Result of the early risk classification (`safety_model.md` §3)."""

    decision: RiskDecision
    rationale: str | None = None  # why; recorded into trace/audit (audit_log.md)
    hazard_signals: list[str] = Field(default_factory=list)  # matched hazard signals
    escalate: bool = False  # ambiguous high-stakes -> human/operator escalation

    @property
    def is_blocked(self) -> bool:
        """Whether capability work is forbidden (refuse/escalate)."""
        return self.decision is RiskDecision.BLOCK

    @property
    def allows_capabilities(self) -> bool:
        """Whether the run may proceed to capability execution."""
        return self.decision is not RiskDecision.BLOCK

    @property
    def forces_review_gate(self) -> bool:
        """Whether any actionable output must pass the human-review gate regardless (§3)."""
        return self.decision is RiskDecision.RESTRICT
