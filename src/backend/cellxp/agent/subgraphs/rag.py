"""Literature-grounding capability subgraph (X2, FR-20)."""

from __future__ import annotations

from collections.abc import Callable

from cellxp.agent.state import (
    AgentState,
    ExecutionCursor,
    NormalizedInputs,
    RunError,
    Step,
    Subtask,
)
from cellxp.domain.clock import utc_now_iso
from cellxp.domain.enums import TaskStatus
from cellxp.services.base import ServiceOutcome
from cellxp.services.rag.schemas import ContextRequest
from cellxp.services.rag.service import RagService
from cellxp.services.reference.genome import ReferenceGenomeService

_Node = Callable[[AgentState], dict[str, object]]


def build_subgraph(
    *,
    reference_service: ReferenceGenomeService | None = None,
    rag_service: RagService | None = None,
) -> _Node:
    """Return a RAG node with injectable reference and retrieval services."""
    ref_svc = reference_service if reference_service is not None else ReferenceGenomeService()
    rag_svc = rag_service if rag_service is not None else RagService()

    def _run(state: AgentState) -> dict[str, object]:
        cursor = ExecutionCursor.model_validate(state.get("cursor", {}))
        subtasks = [
            Subtask.model_validate(item).model_copy(deep=True) for item in state.get("subtasks", [])
        ]
        active = next((item for item in subtasks if item.id == cursor.active_subtask_id), None)
        if active is None:
            return {}

        inputs = NormalizedInputs.model_validate(state.get("normalized_inputs", {}))
        query = _query_for(state, active)
        steps: list[Step] = []

        # Step 1: formulate the grounding query and validate biological framing (RGS-1).
        formulate_started = utc_now_iso()
        if query is None:
            return _fail(
                active,
                subtasks,
                steps,
                "formulate_queries",
                formulate_started,
                "rag subgraph: no claim, topic, entity, or user query to ground",
                "MissingInput",
            )

        catalog = ref_svc.list_supported_references()
        steps.extend(catalog.steps)
        if inputs.organism is not None or inputs.assembly is not None:
            assemblies = catalog.value.assemblies if catalog.value else []
            valid = any(
                (inputs.organism is None or item.organism == inputs.organism)
                and (inputs.assembly is None or item.name == inputs.assembly)
                for item in assemblies
            )
            if not valid:
                return _fail(
                    active,
                    subtasks,
                    steps,
                    "formulate_queries",
                    formulate_started,
                    "rag subgraph: organism/assembly is not in the reference catalog",
                    "ValidationError",
                )
        steps.append(
            Step(
                subtask_id=active.id,
                name="formulate_queries",
                params={"query": query},
                status=TaskStatus.DONE,
                started_at=formulate_started,
                finished_at=utc_now_iso(),
            )
        )

        # Steps 2-4 are represented by the backend's ranked context operation.
        retrieve_started = utc_now_iso()
        result = rag_svc.answer_context(
            ContextRequest(
                query=query,
                organism=inputs.organism,
                assembly=inputs.assembly,
            )
        )
        steps.extend(result.steps)
        if result.outcome is ServiceOutcome.FAILURE:
            message = result.error.message if result.error else "RAG backend failed"
            return _fail(
                active,
                subtasks,
                steps,
                "retrieve_rank_and_extract",
                retrieve_started,
                message,
                "RetrievalError",
            )

        steps.append(
            Step(
                subtask_id=active.id,
                name="retrieve_rank_and_extract",
                weight="heavy",
                tool="rag",
                status=TaskStatus.DONE,
                started_at=retrieve_started,
                finished_at=utc_now_iso(),
            )
        )
        active.status = TaskStatus.DONE
        output: dict[str, object] = {
            "subtasks": subtasks,
            "steps": steps,
            "evidence": result.evidence,
            "artifacts": result.artifacts,
        }
        return output

    return _run


def _query_for(state: AgentState, active: Subtask) -> str | None:
    for key in ("query", "claim", "topic"):
        value = active.inputs.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    user_query = state.get("user_query")
    if isinstance(user_query, str) and user_query.strip():
        return user_query.strip()
    inputs = NormalizedInputs.model_validate(state.get("normalized_inputs", {}))
    if inputs.identifiers:
        return " ".join(inputs.identifiers)
    return None


def _fail(
    active: Subtask,
    subtasks: list[Subtask],
    steps: list[Step],
    step_name: str,
    started: str,
    message: str,
    kind: str,
) -> dict[str, object]:
    active.status = TaskStatus.FAILED
    steps.append(
        Step(
            subtask_id=active.id,
            name=step_name,
            status=TaskStatus.FAILED,
            error=message,
            started_at=started,
            finished_at=utc_now_iso(),
        )
    )
    return {
        "subtasks": subtasks,
        "steps": steps,
        "evidence": [],
        "artifacts": [],
        "errors": [RunError(subtask_id=active.id, kind=kind, message=message)],
    }


run = build_subgraph()
