"""Early purpose-aware safety gate (FR-3, FR-33/34)."""

from __future__ import annotations

from cellxp.agent.state import AgentState
from cellxp.domain.enums import RiskDecision
from cellxp.domain.safety import RiskAssessment

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


def run(state: AgentState) -> dict[str, object]:
    query = state.get("user_query", "").lower()
    signals: list[str] = []
    for signal, (purpose_words, target_words) in _HAZARDOUS_PURPOSES.items():
        if any(word in query for word in purpose_words) and any(
            word in query for word in target_words
        ):
            signals.append(signal)

    if signals:
        assessment = RiskAssessment(
            decision=RiskDecision.BLOCK,
            rationale="The request's stated purpose would increase biological hazard.",
            hazard_signals=signals,
        )
    elif any(phrase in query for phrase in _SENSITIVE_CONTEXT):
        assessment = RiskAssessment(
            decision=RiskDecision.RESTRICT,
            rationale="Sensitive dual-use context requires additional review of actionable output.",
            hazard_signals=[phrase for phrase in _SENSITIVE_CONTEXT if phrase in query],
        )
    else:
        assessment = RiskAssessment(
            decision=RiskDecision.ALLOW,
            rationale="No hazardous purpose was identified in the request.",
        )
    return {"risk": assessment}
