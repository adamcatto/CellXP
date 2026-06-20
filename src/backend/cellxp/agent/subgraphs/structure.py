"""Structure capability subgraph (X3, FR-18).

Predicts 3D structure (protein / nucleic-acid / complex), chromatin contacts, or DNA shape
with per-residue confidence, then emits the corresponding artifacts.

Design (mirrors `variant_effect.py`):
- `build_subgraph(...)` is a factory accepting injectable service instances so tests can
  supply mock backends without touching the global registry.
- `run` is the default node (no structure backend configured) wired into `graph.py`.

Pure structure prediction is analysis — never actionable. Generative design (FR-18a) is
review-gated and handled separately (X6), so this subgraph never sets `is_actionable`.

Steps emitted (FR-24 run-trace completeness):
  1. classify_structure_task  (light) — determine task + validate inputs
  2. validate_reference       (light, genomic only) — RGS-1 assembly check
  3. call_structure_oracle    (heavy) — ESMFold / Boltz-2 / Orca / DNAshapeR
"""

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
from cellxp.services.reference.genome import ReferenceGenomeService
from cellxp.services.structure.schemas import (
    ContactMapRequest,
    DnaShapeRequest,
    StructureRequest,
)
from cellxp.services.structure.service import StructureService
from cellxp.services.structure.transforms import classify_structure_task

_GENOMIC_KINDS = frozenset({"contacts", "dna_shape"})

# Node type alias (same signature as all capability nodes).
_Node = Callable[[AgentState], dict[str, object]]


def build_subgraph(
    *,
    reference_service: ReferenceGenomeService | None = None,
    structure_service: StructureService | None = None,
) -> _Node:
    """Return a structure node with the given (or default) service instances."""
    ref_svc = reference_service if reference_service is not None else ReferenceGenomeService()
    struct_svc = structure_service if structure_service is not None else StructureService()

    def _run(state: AgentState) -> dict[str, object]:
        cursor = ExecutionCursor.model_validate(state.get("cursor", {}))
        subtasks = [
            Subtask.model_validate(s).model_copy(deep=True) for s in state.get("subtasks", [])
        ]
        active = next((s for s in subtasks if s.id == cursor.active_subtask_id), None)
        if active is None:
            return {}

        inputs = NormalizedInputs.model_validate(state.get("normalized_inputs", {}))
        interval = inputs.intervals[0] if inputs.intervals else None
        hint = active.inputs.get("kind") if isinstance(active.inputs, dict) else None

        steps: list[Step] = []
        evidence = []
        artifacts = []
        errors: list[RunError] = []

        # --- Step 1: classify the structure task (light) ---
        classify_started = utc_now_iso()
        kind = classify_structure_task(
            sequences=inputs.sequences, interval=interval, hint=hint
        )
        if kind is None:
            active.status = TaskStatus.FAILED
            msg = "structure subgraph: no sequence or interval in normalized_inputs"
            steps.append(
                Step(
                    subtask_id=active.id,
                    name="classify_structure_task",
                    status=TaskStatus.FAILED,
                    error=msg,
                    started_at=classify_started,
                    finished_at=utc_now_iso(),
                )
            )
            return {
                "subtasks": subtasks,
                "steps": steps,
                "errors": [RunError(subtask_id=active.id, kind="MissingInput", message=msg)],
            }

        steps.append(
            Step(
                subtask_id=active.id,
                name="classify_structure_task",
                params={"kind": kind},
                status=TaskStatus.DONE,
                started_at=classify_started,
                finished_at=utc_now_iso(),
            )
        )

        # --- Step 2: reference validation for genomic structure (light, RGS-1) ---
        if kind in _GENOMIC_KINDS:
            val_started = utc_now_iso()
            assembly = inputs.assembly
            if assembly is None or interval is None:
                active.status = TaskStatus.FAILED
                msg = f"{kind} structure requires an assembly-framed genomic interval"
                steps.append(
                    Step(
                        subtask_id=active.id,
                        name="validate_reference",
                        status=TaskStatus.FAILED,
                        error=msg,
                        started_at=val_started,
                        finished_at=utc_now_iso(),
                    )
                )
                return {
                    "subtasks": subtasks,
                    "steps": steps,
                    "errors": [RunError(subtask_id=active.id, kind="MissingInput", message=msg)],
                }

            catalog = ref_svc.list_supported_references()
            steps.extend(catalog.steps)
            supported = {a.name for a in catalog.value.assemblies} if catalog.value else set()
            if assembly not in supported:
                active.status = TaskStatus.FAILED
                msg = f"assembly {assembly!r} not in reference catalog"
                steps.append(
                    Step(
                        subtask_id=active.id,
                        name="validate_reference",
                        status=TaskStatus.FAILED,
                        error=msg,
                        started_at=val_started,
                        finished_at=utc_now_iso(),
                    )
                )
                return {
                    "subtasks": subtasks,
                    "steps": steps,
                    "errors": [
                        RunError(subtask_id=active.id, kind="ValidationError", message=msg)
                    ],
                }
            steps.append(
                Step(
                    subtask_id=active.id,
                    name="validate_reference",
                    status=TaskStatus.DONE,
                    started_at=val_started,
                    finished_at=utc_now_iso(),
                )
            )

        # --- Step 3: predict (heavy) ---
        predict_started = utc_now_iso()
        if kind in _GENOMIC_KINDS:
            organism = inputs.organism or "Homo sapiens"
            if kind == "contacts":
                result = struct_svc.predict_contacts(
                    ContactMapRequest(
                        interval=interval, organism=organism, assembly=inputs.assembly
                    )
                )
            else:  # dna_shape
                result = struct_svc.predict_dna_shape(
                    DnaShapeRequest(
                        interval=interval, organism=organism, assembly=inputs.assembly
                    )
                )
        else:
            result = struct_svc.predict_structure(
                StructureRequest(
                    kind=kind,  # type: ignore[arg-type]
                    sequences=inputs.sequences,
                    organism=inputs.organism,
                    assembly=inputs.assembly,
                )
            )

        steps.extend(result.steps)
        evidence.extend(result.evidence)
        artifacts.extend(result.artifacts)

        if result.outcome is ServiceOutcome.FAILURE and result.error:
            errors.append(
                RunError(
                    subtask_id=active.id,
                    kind="StructureError",
                    message=result.error.message,
                )
            )

        predict_status = (
            TaskStatus.FAILED if result.outcome is ServiceOutcome.FAILURE else TaskStatus.DONE
        )
        steps.append(
            Step(
                subtask_id=active.id,
                name="call_structure_oracle",
                tool="structure",
                weight="heavy",
                status=predict_status,
                started_at=predict_started,
                finished_at=utc_now_iso(),
            )
        )

        # UNSUPPORTED (no backend) is a non-error path; only a FAILURE fails the subtask.
        active.status = (
            TaskStatus.FAILED if result.outcome is ServiceOutcome.FAILURE else TaskStatus.DONE
        )

        out: dict[str, object] = {
            "subtasks": subtasks,
            "steps": steps,
            "evidence": evidence,
            "artifacts": artifacts,
        }
        if errors:
            out["errors"] = errors
        return out

    return _run


# Default node: no structure backend configured (development / CI mode).
run = build_subgraph()
