"""Variant-effect capability subgraph (N5, FR-13).

Proves the architecture end-to-end: reference validation → oracle selection →
AlphaGenome/Evo 2 scoring → binding delta (mammalian) → evidence + artifact emission.

Design:
- `build_subgraph(...)` is a factory that accepts injectable service instances so
  tests can provide mock backends without touching the global registry.
- `run` is the default node (no model backends configured) wired into `graph.py`.

Steps emitted (FR-24 run-trace completeness):
  1. extract_variant_context  (light) — validate + locate variant
  2. call_effect_oracle       (light/heavy) — AlphaGenome or Evo 2 invocation
  3. compute_binding_delta    (light, mammalian only) — occupancy changes
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
from cellxp.domain.artifacts import ArtifactRef
from cellxp.domain.clock import utc_now_iso
from cellxp.domain.enums import OrganismClass, TaskStatus
from cellxp.domain.evidence import EvidenceItem
from cellxp.services.alphagenome.client import AlphaGenomeService
from cellxp.services.alphagenome.schemas import VariantEffectRequest, select_oracle
from cellxp.services.base import ServiceOutcome
from cellxp.services.binding.delta import BindingDeltaRequest
from cellxp.services.binding.service import BindingService
from cellxp.services.reference.genome import (
    SPECIES_PROFILES,
    ReferenceGenomeService,
    VariantValidationRequest,
)

_MAMMALIAN = frozenset({OrganismClass.MAMMALIAN})

# Node type alias (same signature as all capability nodes).
_Node = Callable[[AgentState], dict[str, object]]


def build_subgraph(
    *,
    reference_service: ReferenceGenomeService | None = None,
    alphagenome_service: AlphaGenomeService | None = None,
    binding_service: BindingService | None = None,
) -> _Node:
    """Return a variant_effect node with the given (or default) service instances."""
    ref_svc = reference_service if reference_service is not None else ReferenceGenomeService()
    ag_svc = alphagenome_service if alphagenome_service is not None else AlphaGenomeService()
    bind_svc = binding_service if binding_service is not None else BindingService()

    def _run(state: AgentState) -> dict[str, object]:
        # --- identify active subtask ---
        cursor = ExecutionCursor.model_validate(state.get("cursor", {}))
        subtasks = [
            Subtask.model_validate(s).model_copy(deep=True) for s in state.get("subtasks", [])
        ]
        active = next(
            (s for s in subtasks if s.id == cursor.active_subtask_id), None
        )
        if active is None:
            return {}

        inputs = NormalizedInputs.model_validate(state.get("normalized_inputs", {}))

        if not inputs.variants:
            active.status = TaskStatus.FAILED
            msg = "variant_effect subgraph: no variants in normalized_inputs"
            return {
                "subtasks": subtasks,
                "steps": [
                    Step(
                        subtask_id=active.id,
                        name="extract_variant_context",
                        status=TaskStatus.FAILED,
                        error=msg,
                        started_at=utc_now_iso(),
                        finished_at=utc_now_iso(),
                    )
                ],
                "errors": [RunError(subtask_id=active.id, kind="MissingInput", message=msg)],
            }

        organism = inputs.organism or "Homo sapiens"
        assembly = inputs.assembly
        variant = inputs.variants[0]

        steps: list[Step] = []
        evidence: list[EvidenceItem] = []
        artifacts: list[ArtifactRef] = []
        errors: list[RunError] = []

        # --- Step 1: extract variant context + validate (light) ---
        ctx_started = utc_now_iso()
        profile = SPECIES_PROFILES.get(organism)
        organism_class = profile.organism_class if profile else None

        if assembly:
            val = ref_svc.validate_variant(
                VariantValidationRequest(
                    variant=variant, organism=organism, assembly=assembly
                )
            )
            steps.extend(val.steps)
            if (
                val.outcome is ServiceOutcome.OK
                and val.value is not None
                and not val.value.valid
            ):
                active.status = TaskStatus.FAILED
                msg = f"variant validation failed: {val.value.fail_reason}"
                steps.append(
                    Step(
                        subtask_id=active.id,
                        name="extract_variant_context",
                        status=TaskStatus.FAILED,
                        error=msg,
                        started_at=ctx_started,
                        finished_at=utc_now_iso(),
                    )
                )
                return {
                    "subtasks": subtasks,
                    "steps": steps,
                    "evidence": evidence,
                    "errors": [RunError(subtask_id=active.id, kind="ValidationError", message=msg)],
                }

        steps.append(
            Step(
                subtask_id=active.id,
                name="extract_variant_context",
                status=TaskStatus.DONE,
                started_at=ctx_started,
                finished_at=utc_now_iso(),
            )
        )

        # --- Step 2: call effect oracle (heavy) ---
        oracle_started = utc_now_iso()
        oracle = select_oracle(organism)
        ag_result = ag_svc.score_variants(
            VariantEffectRequest(
                variants=[variant],
                organism=organism,
                assembly=assembly or "GRCh38",
            )
        )
        steps.extend(ag_result.steps)
        evidence.extend(ag_result.evidence)
        artifacts.extend(ag_result.artifacts)

        oracle_status = (
            TaskStatus.DONE
            if ag_result.ok
            else TaskStatus.FAILED
            if ag_result.outcome is ServiceOutcome.FAILURE
            else TaskStatus.DONE  # UNSUPPORTED is a non-error path; subgraph still completes
        )
        if ag_result.outcome is ServiceOutcome.FAILURE and ag_result.error:
            errors.append(
                RunError(
                    subtask_id=active.id,
                    kind="OracleError",
                    message=ag_result.error.message,
                )
            )
        steps.append(
            Step(
                subtask_id=active.id,
                name="call_effect_oracle",
                tool=oracle,
                status=oracle_status,
                started_at=oracle_started,
                finished_at=utc_now_iso(),
            )
        )

        # --- Step 3: binding delta (mammalian only, light) ---
        if organism_class in _MAMMALIAN and assembly:
            bind_started = utc_now_iso()
            bind_result = bind_svc.score_binding_delta(
                BindingDeltaRequest(
                    variant=variant, organism=organism, assembly=assembly
                )
            )
            steps.extend(bind_result.steps)
            evidence.extend(bind_result.evidence)
            artifacts.extend(bind_result.artifacts)
            steps.append(
                Step(
                    subtask_id=active.id,
                    name="compute_binding_delta",
                    tool="binding",
                    status=TaskStatus.DONE,
                    started_at=bind_started,
                    finished_at=utc_now_iso(),
                )
            )

        # --- Mark subtask complete ---
        active.status = TaskStatus.DONE

        result: dict[str, object] = {
            "subtasks": subtasks,
            "steps": steps,
            "evidence": evidence,
            "artifacts": artifacts,
        }
        if errors:
            result["errors"] = errors
        return result

    return _run


# Default node: no model backends configured (development / CI mode).
run = build_subgraph()
