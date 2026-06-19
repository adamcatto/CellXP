from typing import Any, TypedDict
from typing_extensions import Annotated
from operator import add

class AgentState(TypedDict, total=False):
    messages: Annotated[list[Any], add]
    user_query: str
    intent: str
    subtasks: list[dict[str, Any]]
    evidence: Annotated[list[dict[str, Any]], add]
    artifacts: Annotated[list[dict[str, Any]], add]
    final_report: str
