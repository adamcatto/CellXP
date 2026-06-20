"""Always produce a typed terminal response, including refusal and partial-result paths."""

from __future__ import annotations

from cellxp.agent.state import AgentState, Message, Plan, Report, RunError
from cellxp.domain.enums import IntentType, RunStatus
from cellxp.domain.safety import RiskAssessment


def run(state: AgentState) -> dict[str, object]:
    risk = RiskAssessment.model_validate(state["risk"]) if state.get("risk") else None
    intent = IntentType(state.get("intent", IntentType.AMBIGUOUS))
    errors = [RunError.model_validate(error) for error in state.get("errors", [])]

    if risk and risk.is_blocked:
        markdown = (
            "I can’t help optimize a biological system for increased hazard. I can help with "
            "risk assessment, detection, attenuation, or other defensive analysis instead."
        )
    elif intent is IntentType.OUT_OF_DOMAIN:
        markdown = (
            "That request is outside CellXP’s molecular-biology scope. Ask about DNA, RNA, "
            "proteins, metabolites, molecular interactions, or biological constructs."
        )
    elif errors:
        completed = sum(
            1
            for subtask in state.get("subtasks", [])
            if getattr(subtask, "status", None) == "done"
            or (isinstance(subtask, dict) and subtask.get("status") == "done")
        )
        markdown = (
            f"CellXP understood and planned the request, but capability execution returned "
            f"{len(errors)} recoverable issue(s). {completed} subtask(s) completed; inspect the "
            "run errors for the missing results."
        )
    elif state.get("plan"):
        plan = Plan.model_validate(state["plan"])
        markdown = f"CellXP completed the {plan.kind.value} analysis plan."
    else:
        markdown = "CellXP could not construct an analysis plan from the available information."

    report = Report(markdown=markdown, limitations=[error.message for error in errors])
    return {
        "final_report": report,
        "messages": [Message(role="assistant", content=markdown)],
        "status": RunStatus.COMPLETED,
    }
