"""CRISPR design service (X5, FR-15, CRS-1..5)."""

from __future__ import annotations

from collections.abc import Callable
from typing import TypeVar

from pydantic import BaseModel

from cellxp.agent.state import RunError, Step
from cellxp.domain.artifacts import ArtifactRef
from cellxp.domain.clock import utc_now_iso
from cellxp.domain.enums import ArtifactType, SourceKind, TaskStatus
from cellxp.domain.evidence import EvidenceItem, Provenance
from cellxp.services.base import Service, ServiceResult
from cellxp.services.reference import ASSEMBLY_CATALOG, SPECIES_PROFILES
from cellxp.services.registry import registry

from .schemas import (
    CrisprBackend, CrisprRequest, CrisprResult, EditOutcomeRequest, EditOutcomeResult,
    GuideScoringRequest, GuideScoringResult, OffTargetRequest, OffTargetResult,
)

T = TypeVar("T", bound=BaseModel)


@registry.register
class CrisprService(Service):
    name = "crispr"

    def __init__(self, *, backend: CrisprBackend | None = None, configure: bool = True) -> None:
        if backend is None and configure:
            from .backends import crispr_backend_from_environment
            backend = crispr_backend_from_environment()
        self._backend = backend

    def design_guides(self, request: CrisprRequest) -> ServiceResult[CrisprResult]:
        return self._call(
            "design_guides", request, lambda: _require_backend(self._backend).design_guides(request)
        )

    def enumerate_off_targets(self, request: OffTargetRequest) -> ServiceResult[OffTargetResult]:
        return self._call(
            "enumerate_off_targets", request,
            lambda: _require_backend(self._backend).enumerate_off_targets(request), heavy=True,
        )

    def score_on_target(self, request: GuideScoringRequest) -> ServiceResult[GuideScoringResult]:
        return self._call(
            "score_on_target", request,
            lambda: _require_backend(self._backend).score_on_target(request), heavy=True,
        )

    def predict_edit_outcomes(self, request: EditOutcomeRequest) -> ServiceResult[EditOutcomeResult]:
        return self._call(
            "predict_edit_outcomes", request,
            lambda: _require_backend(self._backend).predict_edit_outcomes(request), heavy=True,
        )

    def _call(
        self, operation: str, request: BaseModel, invoke: Callable[[], T], *, heavy: bool = False
    ) -> ServiceResult[T]:
        started = utc_now_iso()
        organism = str(getattr(request, "organism"))
        assembly = str(getattr(request, "assembly"))
        issue = _coverage_issue(organism, assembly)
        if issue:
            return ServiceResult.unsupported(issue, steps=[_step(operation, started, heavy)])
        if self._backend is None:
            return ServiceResult.unsupported(
                f"{operation} requires a CRISPR backend; none is configured",
                steps=[_step(operation, started, heavy)],
            )
        try:
            value = invoke()
        except Exception as exc:  # noqa: BLE001
            return ServiceResult.failed(
                RunError(kind="BackendError", message=str(exc)),
                steps=[_step(operation, started, heavy, error=str(exc))],
            )
        steps = [_step(operation, started, heavy)]
        if _empty(value):
            return ServiceResult.empty("no feasible CRISPR candidates", steps=steps)
        evidence = _evidence(operation, value, organism, assembly)
        return ServiceResult.succeeded(
            value, steps=steps, evidence=evidence, artifacts=_artifacts(operation, value, evidence)
        )


def _coverage_issue(organism: str, assembly: str) -> str | None:
    if organism not in SPECIES_PROFILES:
        return f"organism {organism!r} is not in the species catalog"
    info = ASSEMBLY_CATALOG.get(assembly)
    if info is None or info.organism != organism:
        return f"assembly {assembly!r} is not catalogued for organism {organism!r}"
    return None


def _require_backend(backend: CrisprBackend | None) -> CrisprBackend:
    assert backend is not None
    return backend


def _empty(value: BaseModel) -> bool:
    records = getattr(value, "guides", None)
    hits = getattr(value, "hits", None)
    scores = getattr(value, "scores", None)
    efficiencies = getattr(value, "efficiencies", None)
    return records == [] or hits == {} or scores == {} or efficiencies == {}


def _evidence(operation: str, value: BaseModel, organism: str, assembly: str) -> list[EvidenceItem]:
    guides = getattr(value, "guides", [])
    if guides:
        return [
            EvidenceItem(
                source=guide.provenance.tool or "crispr_backend",
                source_kind=SourceKind.MODEL,
                claim=f"Candidate guide {guide.spacer} has predicted on/off-target performance",
                value={"on_target": guide.on_target_score, "specificity": guide.specificity_score},
                confidence=guide.confidence,
                provenance=guide.provenance.model_copy(
                    update={"inputs": {"organism": organism, "assembly": assembly}}
                ),
            )
            for guide in guides
        ]
    from cellxp.domain.enums import ConfidenceBand
    from cellxp.domain.evidence import Confidence
    return [EvidenceItem(
        source="crispr_backend", source_kind=SourceKind.COMPUTATION,
        claim=f"CRISPR {operation} completed",
        confidence=Confidence(band=ConfidenceBand.MEDIUM, basis="configured CRISPR backend"),
        provenance=Provenance(tool=operation, tool_version="unknown",
                              inputs={"organism": organism, "assembly": assembly}),
    )]


def _artifacts(operation: str, value: BaseModel, evidence: list[EvidenceItem]) -> list[ArtifactRef]:
    ids = [item.id for item in evidence]
    artifacts: list[ArtifactRef] = []
    guides = getattr(value, "guides", [])
    if guides:
        artifacts.append(ArtifactRef(
            type=ArtifactType.GUIDE_TABLE, title="Candidate CRISPR guide pool",
            storage_ref=getattr(value, "storage_ref", None),
            summary={"guide_count": len(guides), "editing_system": getattr(value, "editing_system")},
            evidence_ids=ids, actionable=True,
        ))
        if getattr(value, "off_target_storage_ref", None):
            artifacts.append(ArtifactRef(
                type=ArtifactType.OFF_TARGET_TABLE, title="Candidate guide off-target profile",
                storage_ref=getattr(value, "off_target_storage_ref"), evidence_ids=ids,
                actionable=True,
            ))
    elif operation == "enumerate_off_targets" and getattr(value, "storage_ref", None):
        artifacts.append(ArtifactRef(
            type=ArtifactType.OFF_TARGET_TABLE, title="CRISPR off-target profile",
            storage_ref=getattr(value, "storage_ref"), evidence_ids=ids, actionable=True,
        ))
    return artifacts


def _step(name: str, started: str, heavy: bool, error: str | None = None) -> Step:
    return Step(
        name=name, tool="crispr_backend", weight="heavy" if heavy else "light",
        status=TaskStatus.FAILED if error else TaskStatus.DONE, started_at=started,
        finished_at=utc_now_iso(), error=error,
    )
