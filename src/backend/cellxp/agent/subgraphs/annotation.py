"""Sequence annotation capability subgraph (L1, FR-16).

Annotates genomic intervals or uploaded FASTA via the Reference Genome Service.
When no annotation database backend is configured the subgraph completes honestly
(roadmap L1) instead of failing with the generic N3 scaffold sentinel.

Steps emitted (FR-24 run-trace completeness):
  1. classify_scope       (light) — interval vs de novo sequence
  2. validate_reference   (light) — RGS-1 assembly/organism check
  3. call_annotation      (heavy) — gene finding / feature lookup backends
"""

from __future__ import annotations

from collections.abc import Callable

from cellxp.agent.state import (
    AgentState,
    ExecutionCursor,
    NormalizedInputs,
    RawInput,
    RunError,
    Step,
    Subtask,
)
from cellxp.domain.artifacts import ArtifactRef, CoordinateFrame
from cellxp.domain.clock import utc_now_iso
from cellxp.domain.enums import (
    ArtifactType,
    ConfidenceBand,
    CoordinateSystem,
    SourceKind,
    Strand,
    TaskStatus,
)
from cellxp.domain.evidence import Confidence, EvidenceItem, Provenance
from cellxp.domain.models import GenomicInterval
from cellxp.services.base import ServiceOutcome, ServiceResult
from cellxp.services.reference import EntityResolveRequest, ReferenceGenomeService
from cellxp.services.reference.annotations import (
    AnnotationFeature,
    AnnotationRequest,
    AnnotationResult,
)

_Node = Callable[[AgentState], dict[str, object]]

_INLINE_SEQUENCE_MSG = (
    "de novo sequence annotation (roadmap L1) requires a FASTA upload reference; "
    "paste-only sequences are not yet dispatched to gene finders"
)


def build_subgraph(
    *,
    reference_service: ReferenceGenomeService | None = None,
) -> _Node:
    """Return an annotation node with an injectable reference service."""
    ref_svc = reference_service if reference_service is not None else ReferenceGenomeService()

    def _run(state: AgentState) -> dict[str, object]:
        cursor = ExecutionCursor.model_validate(state.get("cursor", {}))
        subtasks = [
            Subtask.model_validate(item).model_copy(deep=True) for item in state.get("subtasks", [])
        ]
        active = next((item for item in subtasks if item.id == cursor.active_subtask_id), None)
        if active is None:
            return {}

        inputs = NormalizedInputs.model_validate(state.get("normalized_inputs", {}))
        steps: list[Step] = []
        evidence: list[EvidenceItem] = []
        artifacts: list[ArtifactRef] = []
        errors: list[RunError] = []

        # --- Step 0: resolve gene symbol → interval when needed (FR-16 / entity_resolver) ---
        resolve_started = utc_now_iso()
        inputs, resolve_steps, resolve_error = _resolve_gene_interval(
            inputs, state, ref_svc, active.id, resolve_started
        )
        steps.extend(resolve_steps)
        if resolve_error is not None:
            active.status = TaskStatus.FAILED
            return {
                "subtasks": subtasks,
                "steps": steps,
                "errors": [resolve_error],
            }

        # --- Step 1: classify scope (light) ---
        classify_started = utc_now_iso()
        scope = _classify_scope(inputs, state)
        if scope is None:
            active.status = TaskStatus.FAILED
            msg = "annotation subgraph: provide a genomic interval or uploaded FASTA sequence"
            steps.append(
                Step(
                    subtask_id=active.id,
                    name="classify_scope",
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
                name="classify_scope",
                params={"scope": scope},
                status=TaskStatus.DONE,
                started_at=classify_started,
                finished_at=utc_now_iso(),
            )
        )

        # --- Step 2: validate reference framing (light, RGS-1) ---
        validate_started = utc_now_iso()
        if inputs.organism is None or inputs.assembly is None:
            active.status = TaskStatus.FAILED
            msg = "annotation requires organism and assembly before coordinate operations (FR-11)"
            steps.append(
                Step(
                    subtask_id=active.id,
                    name="validate_reference",
                    status=TaskStatus.FAILED,
                    error=msg,
                    started_at=validate_started,
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
        assemblies = catalog.value.assemblies if catalog.value else []
        if not any(
            item.organism == inputs.organism and item.name == inputs.assembly for item in assemblies
        ):
            active.status = TaskStatus.FAILED
            msg = f"assembly {inputs.assembly!r} for {inputs.organism!r} is not in the reference catalog"
            steps.append(
                Step(
                    subtask_id=active.id,
                    name="validate_reference",
                    status=TaskStatus.FAILED,
                    error=msg,
                    started_at=validate_started,
                    finished_at=utc_now_iso(),
                )
            )
            return {
                "subtasks": subtasks,
                "steps": steps,
                "errors": [RunError(subtask_id=active.id, kind="ValidationError", message=msg)],
            }

        steps.append(
            Step(
                subtask_id=active.id,
                name="validate_reference",
                status=TaskStatus.DONE,
                started_at=validate_started,
                finished_at=utc_now_iso(),
            )
        )

        # --- Step 3: annotate (heavy) ---
        annotate_started = utc_now_iso()
        request = _annotation_request(inputs, scope, state)
        if request is None:
            active.status = TaskStatus.DONE
            steps.append(
                Step(
                    subtask_id=active.id,
                    name="call_annotation",
                    tool="reference",
                    weight="heavy",
                    status=TaskStatus.DONE,
                    output_ref=_INLINE_SEQUENCE_MSG,
                    started_at=annotate_started,
                    finished_at=utc_now_iso(),
                )
            )
            return {"subtasks": subtasks, "steps": steps, "evidence": evidence, "artifacts": artifacts}

        result = ref_svc.annotate(request)
        steps.extend(result.steps)
        evidence.extend(
            item.model_copy(update={"subtask_id": active.id}) for item in result.evidence
        )
        artifacts.extend(
            item.model_copy(update={"subtask_id": active.id}) for item in result.artifacts
        )
        if result.outcome is ServiceOutcome.OK and result.value is not None:
            evidence.extend(_evidence_from_features(active.id, result.value))
            artifacts.extend(_artifacts_from_result(active.id, result.value, inputs))

        if result.outcome is ServiceOutcome.FAILURE and result.error:
            errors.append(
                RunError(
                    subtask_id=active.id,
                    kind="AnnotationError",
                    message=result.error.message,
                )
            )

        annotate_status = (
            TaskStatus.FAILED if result.outcome is ServiceOutcome.FAILURE else TaskStatus.DONE
        )
        steps.append(
            Step(
                subtask_id=active.id,
                name="call_annotation",
                tool="reference",
                weight="heavy",
                status=annotate_status,
                output_ref=result.detail,
                started_at=annotate_started,
                finished_at=utc_now_iso(),
            )
        )

        active.status = (
            TaskStatus.FAILED if result.outcome is ServiceOutcome.FAILURE else TaskStatus.DONE
        )
        output: dict[str, object] = {
            "subtasks": subtasks,
            "steps": steps,
            "evidence": evidence,
            "artifacts": artifacts,
        }
        if errors:
            output["errors"] = errors
        return output

    return _run


def _gene_identifiers(inputs: NormalizedInputs) -> list[str]:
    return [item for item in inputs.identifiers if not item.lower().startswith("rs")]


def _resolve_gene_interval(
    inputs: NormalizedInputs,
    state: AgentState,
    ref_svc: ReferenceGenomeService,
    subtask_id: str,
    started: str,
) -> tuple[NormalizedInputs, list[Step], RunError | None]:
    """Resolve a gene symbol to a genomic interval when annotation lacks explicit scope."""
    if inputs.intervals or inputs.sequences or _fasta_ref(state):
        return inputs, [], None

    gene_ids = _gene_identifiers(inputs)
    if not gene_ids:
        return inputs, [], None
    if inputs.organism is None or inputs.assembly is None:
        return inputs, [], None

    result = ref_svc.resolve_entity(
        EntityResolveRequest(
            identifier=gene_ids[0],
            organism=inputs.organism,
            assembly=inputs.assembly,
            type_hint="gene",
        )
    )
    steps = [
        step.model_copy(update={"subtask_id": subtask_id}) for step in result.steps
    ]
    if result.outcome is ServiceOutcome.FAILURE:
        message = result.error.message if result.error else "gene resolution failed"
        steps.append(
            Step(
                subtask_id=subtask_id,
                name="resolve_gene_locus",
                status=TaskStatus.FAILED,
                error=message,
                started_at=started,
                finished_at=utc_now_iso(),
            )
        )
        return inputs, steps, RunError(subtask_id=subtask_id, kind="ValidationError", message=message)
    if result.outcome is ServiceOutcome.UNSUPPORTED:
        message = result.detail or "gene resolution unavailable"
        steps.append(
            Step(
                subtask_id=subtask_id,
                name="resolve_gene_locus",
                status=TaskStatus.FAILED,
                error=message,
                started_at=started,
                finished_at=utc_now_iso(),
            )
        )
        return inputs, steps, RunError(
            subtask_id=subtask_id, kind="UnsupportedReference", message=message
        )
    entity = result.value.entity if result.value is not None else None
    if entity is None or entity.chrom is None or entity.start is None or entity.end is None:
        message = f"gene {gene_ids[0]!r} could not be resolved to genomic coordinates"
        steps.append(
            Step(
                subtask_id=subtask_id,
                name="resolve_gene_locus",
                status=TaskStatus.FAILED,
                error=message,
                started_at=started,
                finished_at=utc_now_iso(),
            )
        )
        return inputs, steps, RunError(subtask_id=subtask_id, kind="MissingInput", message=message)

    updated = inputs.model_copy(deep=True)
    updated.intervals.append(
        GenomicInterval(
            species=entity.organism,
            assembly=entity.assembly,
            chrom=entity.chrom,
            start=entity.start,
            end=entity.end,
            strand=entity.strand or Strand.UNSTRANDED,
        )
    )
    steps.append(
        Step(
            subtask_id=subtask_id,
            name="resolve_gene_locus",
            params={"gene": gene_ids[0], "interval": updated.intervals[-1].model_dump(mode="json")},
            status=TaskStatus.DONE,
            started_at=started,
            finished_at=utc_now_iso(),
        )
    )
    return updated, steps, None


def _classify_scope(inputs: NormalizedInputs, state: AgentState) -> str | None:
    if inputs.intervals:
        return "interval"
    if inputs.sequences or _fasta_ref(state):
        return "sequence"
    return None


def _fasta_ref(state: AgentState) -> str | None:
    for raw in state.get("raw_inputs", []):
        item = RawInput.model_validate(raw)
        if item.kind == "file" and item.file_ref:
            return item.file_ref
    return None


def _annotation_request(
    inputs: NormalizedInputs, scope: str, state: AgentState
) -> AnnotationRequest | None:
    assert inputs.organism is not None and inputs.assembly is not None
    if scope == "interval":
        interval = inputs.intervals[0]
        return AnnotationRequest(
            organism=inputs.organism,
            assembly=inputs.assembly,
            chrom=interval.chrom,
            start=interval.start,
            end=interval.end,
        )
    fasta_ref = _fasta_ref(state)
    if fasta_ref is None:
        return None
    return AnnotationRequest(
        organism=inputs.organism,
        assembly=inputs.assembly,
        fasta_ref=fasta_ref,
    )


def _evidence_from_features(subtask_id: str, result: AnnotationResult) -> list[EvidenceItem]:
    items: list[EvidenceItem] = []
    for feature in result.features[:25]:
        label = feature.name or feature.feature_id
        items.append(
            EvidenceItem(
                subtask_id=subtask_id,
                source=feature.source,
                source_kind=SourceKind.DATABASE,
                claim=f"{feature.feature_type} {label} at {feature.chrom}:{feature.start}-{feature.end}",
                value=feature.model_dump(mode="json"),
                confidence=Confidence(
                    band=ConfidenceBand.MEDIUM,
                    basis="reference annotation database",
                ),
                provenance=Provenance(tool=feature.source, inputs={"organism": result.organism}),
            )
        )
    return items


def _artifacts_from_result(
    subtask_id: str, result: AnnotationResult, inputs: NormalizedInputs
) -> list[ArtifactRef]:
    interval = inputs.intervals[0] if inputs.intervals else None
    frame = CoordinateFrame(
        kind="genomic",
        organism=result.organism,
        assembly=result.assembly,
        contig=interval.chrom if interval is not None else None,
        convention=CoordinateSystem.ZERO_BASED_HALF_OPEN,
    )
    preview = [feature.model_dump(mode="json") for feature in result.features[:50]]
    summary = {
        "feature_count": len(result.features),
        "sources": result.source_databases,
        "preview": preview,
    }
    return [
        ArtifactRef(
            subtask_id=subtask_id,
            type=ArtifactType.GENOME_TRACK,
            title="annotation track",
            storage_ref=result.storage_ref,
            coordinate_frame=frame,
            summary=summary,
        )
    ]


run = build_subgraph()
