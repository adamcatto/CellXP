"""Bounded inverse-design optimizer (X7, FR-18c)."""

from __future__ import annotations

from cellxp.agent.state import RunError, Step
from cellxp.domain.artifacts import ArtifactRef
from cellxp.domain.clock import utc_now_iso
from cellxp.domain.enums import ArtifactType, SourceKind, TaskStatus
from cellxp.domain.evidence import EvidenceItem
from cellxp.services.base import Service, ServiceResult
from cellxp.services.reference import ASSEMBLY_CATALOG, SPECIES_PROFILES
from cellxp.services.registry import registry

from .schemas import (
    CandidateAssessment, CandidateProposal, EditCandidate, InverseDesignBackend,
    InverseDesignRequest, InverseDesignResult,
)


@registry.register
class InverseDesignService(Service):
    name = "inverse_design"

    def __init__(self, *, backend: InverseDesignBackend | None = None) -> None:
        self._backend = backend

    def design(self, request: InverseDesignRequest) -> ServiceResult[InverseDesignResult]:
        issue = _coverage_issue(request)
        if issue:
            return ServiceResult.unsupported(issue, steps=[_step("validate_inverse_objective")])
        if self._backend is None:
            return ServiceResult.unsupported(
                "inverse design requires a forward-oracle/CRISPR backend; none is configured",
                steps=[_step("validate_inverse_objective")],
            )

        steps = [_step("frame_inverse_objective")]
        assessed: list[tuple[CandidateProposal, CandidateAssessment]] = []
        seen: set[tuple[int, str, str]] = set()
        try:
            for iteration in range(request.budget.max_iterations):
                proposals = self._backend.propose(request, iteration)
                proposals = [
                    item for item in proposals
                    if (item.edit.position, item.edit.ref, item.edit.alt) not in seen
                ][: max(0, request.budget.max_candidates - len(seen))]
                if not proposals:
                    break
                seen.update((item.edit.position, item.edit.ref, item.edit.alt) for item in proposals)
                assessments = self._backend.assess(request, proposals)
                if len(assessments) != len(proposals):
                    raise ValueError("backend returned a different number of assessments")
                assessed.extend(zip(proposals, assessments, strict=True))
                steps.extend([_step("propose_candidate_edits"), _step("score_forward_and_feasibility", heavy=True)])
                if len(seen) >= request.budget.max_candidates:
                    break
        except Exception as exc:  # noqa: BLE001
            return ServiceResult.failed(
                RunError(kind="BackendError", message=str(exc)),
                steps=[*steps, _step("inverse_design_search", error=str(exc))],
            )
        if not assessed:
            return ServiceResult.empty("no realizable edits found within search budget", steps=steps)

        candidates = [_candidate(request, proposal, assessment) for proposal, assessment in assessed]
        candidates.sort(key=lambda item: item.score, reverse=True)
        _mark_pareto(candidates)
        target = request.target_effect.magnitude
        target_gap = min(abs(item.predicted_effect - target) for item in candidates) if target is not None else None
        result = InverseDesignResult(
            candidates=candidates, iterations=sum(s.name == "propose_candidate_edits" for s in steps),
            converged=target_gap is not None and target_gap <= 0.05, target_gap=target_gap,
        )
        evidence = [_evidence(item, request) for item in candidates]
        artifact = ArtifactRef(
            type=ArtifactType.GUIDE_TABLE, title="Model-guided candidate edits",
            summary={"candidate_count": len(candidates), "pareto_count": sum(x.pareto_front for x in candidates),
                     "converged": result.converged},
            evidence_ids=[item.id for item in evidence], actionable=True,
        )
        return ServiceResult.succeeded(result, steps=[*steps, _step("rank_pareto_candidates")],
                                       evidence=evidence, artifacts=[artifact])


def _coverage_issue(request: InverseDesignRequest) -> str | None:
    if request.organism not in SPECIES_PROFILES:
        return f"organism {request.organism!r} is not in the species catalog"
    info = ASSEMBLY_CATALOG.get(request.assembly)
    if info is None or info.organism != request.organism:
        return f"assembly {request.assembly!r} is not catalogued for organism {request.organism!r}"
    return None


def _candidate(request, proposal, assessment):
    weights = request.objective_weights
    target = request.target_effect.magnitude
    effect_fit = 1.0 / (1.0 + abs(assessment.predicted_effect - target)) if target is not None else (
        assessment.predicted_effect if request.target_effect.direction in {"increase", "create"}
        else -assessment.predicted_effect
    )
    score = (weights.on_target * effect_fit - weights.off_target * assessment.off_target_penalty
             - weights.collateral * assessment.collateral_penalty
             + weights.feasibility * assessment.feasibility)
    return EditCandidate(
        edit=proposal.edit, editor=proposal.editor, predicted_effect=assessment.predicted_effect,
        off_targets=assessment.off_targets, collateral_penalty=assessment.collateral_penalty,
        feasibility=assessment.feasibility, score=score, confidence=assessment.confidence,
        provenance=assessment.provenance,
    )


def _mark_pareto(candidates: list[EditCandidate]) -> None:
    for item in candidates:
        item.pareto_front = not any(
            other is not item and other.score >= item.score and other.feasibility >= item.feasibility
            and (other.score > item.score or other.feasibility > item.feasibility)
            for other in candidates
        )


def _evidence(candidate: EditCandidate, request: InverseDesignRequest) -> EvidenceItem:
    return EvidenceItem(
        source=candidate.provenance.tool or "inverse_design_backend", source_kind=SourceKind.MODEL,
        claim=f"Candidate edit at {candidate.edit.position} was forward-scored and CRISPR-assessed",
        value={"predicted_effect": candidate.predicted_effect, "score": candidate.score,
               "feasibility": candidate.feasibility}, confidence=candidate.confidence,
        provenance=candidate.provenance.model_copy(update={"inputs": {
            "organism": request.organism, "assembly": request.assembly,
            "readout": request.target_effect.readout,
        }}),
    )


def _step(name: str, *, heavy: bool = False, error: str | None = None) -> Step:
    now = utc_now_iso()
    return Step(name=name, tool="inverse_design", weight="heavy" if heavy else "light",
                status=TaskStatus.FAILED if error else TaskStatus.DONE, started_at=now,
                finished_at=now, error=error)
