"""Early purpose-aware safety gate (FR-3, FR-33/34)."""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

from cellxp.agent.state import AgentState
from cellxp.domain.audit import AGENT_ACTOR, AuditEntry, AuditEventType
from cellxp.domain.enums import RiskDecision
from cellxp.domain.safety import RiskAssessment

if TYPE_CHECKING:
    from cellxp.storage.audit_repository import AuditRepository

_HAZARDOUS_PURPOSES = {
    "enhance_virulence": (("enhance", "increase", "maximize"), ("virulence", "pathogenicity")),
    "enhance_transmission": (
        ("enhance", "increase", "maximize"),
        ("transmission", "transmissibility"),
    ),
    "evade_detection": (("evade", "bypass", "avoid"), ("detection", "screening", "surveillance")),
    "weaponization": (("weaponize", "weaponise"), ("toxin", "pathogen", "virus", "bacteria")),
}
_SENSITIVE_CONTEXT = ("gain of function", "select agent", "pandemic pathogen", "toxin design")

_QUERY_DIGEST_MAX = 200  # chars; avoids storing raw sensitive text in audit payloads (AL-3)


def _digest(query: str) -> str:
    """Truncated query for audit payload — not raw if sensitive (AL-3)."""
    return query[:_QUERY_DIGEST_MAX] if len(query) <= _QUERY_DIGEST_MAX else query[:_QUERY_DIGEST_MAX] + "…"


def _classify(query: str) -> RiskAssessment:
    signals: list[str] = []
    for signal, (purpose_words, target_words) in _HAZARDOUS_PURPOSES.items():
        if any(word in query for word in purpose_words) and any(
            word in query for word in target_words
        ):
            signals.append(signal)

    if signals:
        return RiskAssessment(
            decision=RiskDecision.BLOCK,
            rationale="The request's stated purpose would increase biological hazard.",
            hazard_signals=signals,
        )
    if any(phrase in query for phrase in _SENSITIVE_CONTEXT):
        return RiskAssessment(
            decision=RiskDecision.RESTRICT,
            rationale="Sensitive dual-use context requires additional review of actionable output.",
            hazard_signals=[phrase for phrase in _SENSITIVE_CONTEXT if phrase in query],
        )
    return RiskAssessment(
        decision=RiskDecision.ALLOW,
        rationale="No hazardous purpose was identified in the request.",
    )


def make_risk_classifier(
    audit_repo: "AuditRepository | None" = None,
) -> Callable[[AgentState], dict[str, object]]:
    """Return a risk_classifier node function with an optionally injected audit repository.

    When `audit_repo` is provided every BLOCK or RESTRICT decision is written to the
    audit log as `safety.refused` or `safety.restricted` respectively (AL-1, FR-34).
    The repository is expected to be in an open transaction; commit/rollback is the
    caller's responsibility (typically the graph runner or API layer).
    """

    def _run(state: AgentState) -> dict[str, object]:
        query = state.get("user_query", "").lower()
        assessment = _classify(query)
        run_id: str | None = state.get("run_id")

        if audit_repo is not None:
            if assessment.is_blocked:
                audit_repo.append(
                    event_type=AuditEventType.SAFETY_REFUSED,
                    actor=AGENT_ACTOR,
                    run_id=run_id,
                    payload={
                        "rationale": assessment.rationale,
                        "hazard_signals": assessment.hazard_signals,
                        "query_digest": _digest(query),
                    },
                )
            elif assessment.forces_review_gate:
                audit_repo.append(
                    event_type=AuditEventType.SAFETY_RESTRICTED,
                    actor=AGENT_ACTOR,
                    run_id=run_id,
                    payload={
                        "rationale": assessment.rationale,
                        "hazard_signals": assessment.hazard_signals,
                        "query_digest": _digest(query),
                    },
                )

        return {"risk": assessment}

    return _run


# Default node function — no audit writes (used when graph is built without an audit repo).
run = make_risk_classifier()
