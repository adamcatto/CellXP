"""GWAS/QTL capability subgraph (X1, FR-14)."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Literal

from cellxp.agent.state import AgentState, ExecutionCursor, NormalizedInputs, RunError, Step, Subtask
from cellxp.domain.clock import utc_now_iso
from cellxp.domain.artifacts import ArtifactRef
from cellxp.domain.enums import TaskStatus
from cellxp.domain.evidence import EvidenceItem
from cellxp.services.base import ServiceOutcome
from cellxp.services.gwas import (
    ColocRequest, FineMapRequest, GeneReference, GwasRequest, GwasService, LdRequest,
)
from cellxp.domain.models import GenomicInterval, Variant
from cellxp.services.reference import (
    EntityResolveRequest,
    ReferenceGenomeService,
    SequenceFetchRequest,
    VariantValidationRequest,
)

_Node = Callable[[AgentState], dict[str, object]]


def build_subgraph(
    *,
    reference_service: ReferenceGenomeService | None = None,
    gwas_service: GwasService | None = None,
) -> _Node:
    """Return a GWAS node with injectable reference and statistical backends."""
    ref_svc = reference_service if reference_service is not None else ReferenceGenomeService()
    gwas_svc = gwas_service if gwas_service is not None else GwasService()

    def _run(state: AgentState) -> dict[str, object]:
        cursor = ExecutionCursor.model_validate(state.get("cursor", {}))
        subtasks = [
            Subtask.model_validate(item).model_copy(deep=True)
            for item in state.get("subtasks", [])
        ]
        active = next((item for item in subtasks if item.id == cursor.active_subtask_id), None)
        if active is None:
            return {}

        inputs = NormalizedInputs.model_validate(state.get("normalized_inputs", {}))
        organism = inputs.organism
        assembly = inputs.assembly
        if organism is None or assembly is None:
            return _failure(
                active,
                subtasks,
                "resolve_gwas_subject",
                "GWAS subgraph requires organism and assembly",
                "MissingInput",
            )

        subject = (
            inputs.variants[0]
            if inputs.variants
            else inputs.intervals[0]
            if inputs.intervals
            else GeneReference(identifier=inputs.identifiers[0])
            if inputs.identifiers
            else None
        )
        if subject is None:
            return _failure(
                active,
                subtasks,
                "resolve_gwas_subject",
                "GWAS subgraph requires a variant, locus, or gene identifier",
                "MissingInput",
            )

        steps: list[Step] = []
        evidence = []
        artifacts = []
        validation_started = utc_now_iso()
        validation_unsupported = False
        validation_detail: str | None = None
        if inputs.variants:
            variant_validation = ref_svc.validate_variant(
                VariantValidationRequest(
                    variant=inputs.variants[0], organism=organism, assembly=assembly
                )
            )
            invalid = (
                variant_validation.outcome is ServiceOutcome.OK
                and variant_validation.value is not None
                and not variant_validation.value.valid
            )
            validation_detail = (
                variant_validation.value.fail_reason
                if variant_validation.value is not None
                else variant_validation.detail
            )
            validation_unsupported = variant_validation.outcome is ServiceOutcome.UNSUPPORTED
            steps.extend(variant_validation.steps)
        elif inputs.intervals:
            interval = inputs.intervals[0]
            interval_validation = ref_svc.get_sequence(
                SequenceFetchRequest(
                    organism=organism,
                    assembly=assembly,
                    chrom=interval.chrom,
                    start=interval.start,
                    end=interval.end,
                    strand=interval.strand,
                )
            )
            no_sequence_backend = (
                interval_validation.outcome is ServiceOutcome.UNSUPPORTED
                and interval_validation.detail is not None
                and interval_validation.detail.startswith("sequence extraction requires")
            )
            invalid = interval_validation.outcome is ServiceOutcome.FAILURE or (
                interval_validation.outcome is ServiceOutcome.UNSUPPORTED
                and not no_sequence_backend
            )
            validation_detail = (
                interval_validation.error.message
                if interval_validation.error is not None
                else interval_validation.detail
            )
            steps.extend(interval_validation.steps)
        else:
            entity_validation = ref_svc.resolve_entity(
                EntityResolveRequest(
                    identifier=inputs.identifiers[0],
                    organism=organism,
                    assembly=assembly,
                    type_hint="gene",
                )
            )
            invalid = entity_validation.outcome is ServiceOutcome.FAILURE
            validation_detail = (
                entity_validation.error.message
                if entity_validation.error is not None
                else entity_validation.detail
            )
            validation_unsupported = entity_validation.outcome is ServiceOutcome.UNSUPPORTED
            steps.extend(entity_validation.steps)
        if invalid:
            return _failure(
                active,
                subtasks,
                "resolve_gwas_subject",
                validation_detail or "reference validation failed",
                "ValidationError",
                prior_steps=steps,
                started=validation_started,
            )
        if validation_unsupported:
            return _failure(
                active,
                subtasks,
                "resolve_gwas_subject",
                validation_detail or "reference resolution unavailable",
                "UnsupportedReference",
                prior_steps=steps,
                started=validation_started,
            )
        steps.append(_step(active.id, "resolve_gwas_subject", validation_started))

        query_started = utc_now_iso()
        result = gwas_svc.lookup_associations(
            GwasRequest(
                subject=subject,
                organism=organism,
                assembly=assembly,
                traits=active.inputs.get("traits"),
                tissues=active.inputs.get("tissues"),
                ld_population=active.inputs.get("ld_population"),
                do_finemap=active.inputs.get("do_finemap", True),
                do_coloc=active.inputs.get("do_coloc", True),
            )
        )
        steps.extend(result.steps)
        evidence.extend(result.evidence)
        artifacts.extend(result.artifacts)
        if result.outcome is ServiceOutcome.FAILURE:
            message = result.error.message if result.error else "GWAS backend failed"
            return _failure(
                active,
                subtasks,
                "query_gwas_evidence",
                message,
                "GwasServiceError",
                prior_steps=steps,
                started=query_started,
                evidence=evidence,
                artifacts=artifacts,
            )
        partial_errors: list[RunError] = []
        analysis_interval = _analysis_interval(subject, active.inputs)
        population = active.inputs.get("ld_population")
        if population and analysis_interval is not None:
            ld_result = gwas_svc.compute_ld(LdRequest(
                interval=analysis_interval, organism=organism, assembly=assembly,
                population=str(population),
                lead_variants=list(active.inputs.get("lead_variants", [])),
            ))
            _merge_partial(ld_result, active, "LD", steps, evidence, artifacts, partial_errors)

        stats_ref = active.inputs.get("summary_stats_ref")
        if active.inputs.get("do_finemap", bool(stats_ref)):
            if analysis_interval is None or not stats_ref:
                partial_errors.append(RunError(
                    subtask_id=active.id, kind="MissingSummaryStatistics",
                    message="fine-mapping skipped: interval and summary_stats_ref are required",
                    recoverable=True,
                ))
            else:
                fine_result = gwas_svc.fine_map(FineMapRequest(
                    interval=analysis_interval, organism=organism, assembly=assembly,
                    trait=_primary_trait(active.inputs), population=str(population) if population else None,
                    summary_stats_ref=str(stats_ref),
                    ld_matrix_ref=_optional_str(active.inputs.get("ld_matrix_ref")),
                ))
                _merge_partial(fine_result, active, "fine-mapping", steps, evidence, artifacts,
                               partial_errors)

        gwas_stats = active.inputs.get("gwas_stats_ref")
        qtl_stats = active.inputs.get("qtl_stats_ref")
        if active.inputs.get("do_coloc", bool(gwas_stats and qtl_stats)):
            tissues = list(active.inputs.get("tissues") or [])
            if analysis_interval is None or not gwas_stats or not qtl_stats or not tissues:
                partial_errors.append(RunError(
                    subtask_id=active.id, kind="MissingColocInputs",
                    message=("colocalization skipped: interval, tissues, gwas_stats_ref, and "
                             "qtl_stats_ref are required"),
                    recoverable=True,
                ))
            else:
                coloc_result = gwas_svc.coloc(ColocRequest(
                    interval=analysis_interval, organism=organism, assembly=assembly,
                    trait=_primary_trait(active.inputs), tissues=tissues,
                    gwas_stats_ref=str(gwas_stats), qtl_stats_ref=str(qtl_stats),
                ))
                _merge_partial(coloc_result, active, "colocalization", steps, evidence, artifacts,
                               partial_errors)
        steps.append(
            _step(active.id, "query_gwas_evidence", query_started, tool="gwas", weight="heavy")
        )

        rank_started = utc_now_iso()
        steps.append(_step(active.id, "rank_and_emit_locus", rank_started))
        active.status = TaskStatus.DONE
        output: dict[str, object] = {
            "subtasks": subtasks,
            "steps": steps,
            "evidence": evidence,
            "artifacts": artifacts,
        }
        if partial_errors:
            output["errors"] = partial_errors
        return output

    return _run


def _failure(
    active: Subtask,
    subtasks: list[Subtask],
    name: str,
    message: str,
    kind: str,
    *,
    prior_steps: list[Step] | None = None,
    started: str | None = None,
    evidence: Sequence[EvidenceItem] | None = None,
    artifacts: Sequence[ArtifactRef] | None = None,
) -> dict[str, object]:
    active.status = TaskStatus.FAILED
    steps = list(prior_steps or [])
    steps.append(
        Step(
            subtask_id=active.id,
            name=name,
            status=TaskStatus.FAILED,
            error=message,
            started_at=started or utc_now_iso(),
            finished_at=utc_now_iso(),
        )
    )
    output: dict[str, object] = {
        "subtasks": subtasks,
        "steps": steps,
        "evidence": list(evidence or []),
        "artifacts": list(artifacts or []),
        "errors": [RunError(subtask_id=active.id, kind=kind, message=message)],
    }
    return output


def _step(
    subtask_id: str,
    name: str,
    started: str,
    *,
    tool: str | None = None,
    weight: Literal["light", "heavy"] = "light",
) -> Step:
    return Step(
        subtask_id=subtask_id,
        name=name,
        tool=tool,
        weight=weight,
        status=TaskStatus.DONE,
        started_at=started,
        finished_at=utc_now_iso(),
    )


run = build_subgraph()


def _analysis_interval(subject: object, inputs: dict[str, object]) -> GenomicInterval | None:
    if isinstance(subject, GenomicInterval):
        return subject
    if isinstance(subject, Variant):
        raw_flank = inputs.get("analysis_flank", 500_000)
        flank = int(raw_flank) if isinstance(raw_flank, (str, int)) else 500_000
        return GenomicInterval(
            assembly=subject.assembly,
            chrom=subject.chrom,
            start=max(0, subject.pos - flank),
            end=subject.pos + flank + max(1, len(subject.ref)),
        )
    return None


def _primary_trait(inputs: dict[str, object]) -> str:
    traits = inputs.get("traits")
    return str(traits[0]) if isinstance(traits, list) and traits else "unspecified trait"


def _optional_str(value: object) -> str | None:
    return str(value) if value else None


def _merge_partial(result, active, label, steps, evidence, artifacts, errors) -> None:  # noqa: ANN001
    steps.extend(result.steps)
    evidence.extend(item.model_copy(update={"subtask_id": active.id}) for item in result.evidence)
    artifacts.extend(item.model_copy(update={"subtask_id": active.id}) for item in result.artifacts)
    if result.outcome in {ServiceOutcome.FAILURE, ServiceOutcome.UNSUPPORTED}:
        detail = result.error.message if result.error else result.detail or "unavailable"
        errors.append(RunError(
            subtask_id=active.id, kind="PartialGwasAnalysis",
            message=f"{label} unavailable: {detail}", recoverable=True,
        ))
