"""GWAS/QTL service boundary (X1, FR-14, GWS-1..5)."""

from __future__ import annotations

from collections.abc import Callable
from typing import TypeVar

from pydantic import BaseModel

from cellxp.agent.state import RunError, Step
from cellxp.domain.artifacts import ArtifactRef
from cellxp.domain.clock import utc_now_iso
from cellxp.domain.enums import ArtifactType, ConfidenceBand, SourceKind, TaskStatus
from cellxp.domain.evidence import Confidence, EvidenceItem, Provenance
from cellxp.services.base import Service, ServiceResult
from cellxp.services.reference import ASSEMBLY_CATALOG, SPECIES_PROFILES
from cellxp.services.registry import registry

from .schemas import (
    ColocBatchResult,
    ColocRequest,
    FineMapRequest,
    FineMapResult,
    GwasBackend,
    GwasRequest,
    GwasResult,
    LdRequest,
    LdResult,
)

T = TypeVar("T", bound=BaseModel)


@registry.register
class GwasService(Service):
    """Human statistical-genetics service with an injectable data/tool backend."""

    name = "gwas"

    def __init__(self, *, backend: GwasBackend | None = None, configure: bool = True) -> None:
        if backend is None and configure:
            from .backends import gwas_backend_from_environment
            backend = gwas_backend_from_environment()
        self._backend = backend

    def lookup_associations(self, request: GwasRequest) -> ServiceResult[GwasResult]:
        return self._call(
            "lookup_associations",
            request,
            lambda: _require_backend(self._backend).lookup_associations(request),
        )

    def compute_ld(self, request: LdRequest) -> ServiceResult[LdResult]:
        return self._call(
            "compute_ld",
            request,
            lambda: _require_backend(self._backend).compute_ld(request),
            heavy=True,
        )

    def fine_map(self, request: FineMapRequest) -> ServiceResult[FineMapResult]:
        return self._call(
            "fine_map",
            request,
            lambda: _require_backend(self._backend).fine_map(request),
            heavy=True,
        )

    def coloc(self, request: ColocRequest) -> ServiceResult[ColocBatchResult]:
        return self._call(
            "coloc",
            request,
            lambda: _require_backend(self._backend).coloc(request),
            heavy=True,
        )

    def _call(
        self,
        operation: str,
        request: BaseModel,
        invoke: Callable[[], T],
        *,
        heavy: bool = False,
    ) -> ServiceResult[T]:
        started = utc_now_iso()
        organism = str(getattr(request, "organism"))
        assembly = str(getattr(request, "assembly"))
        unsupported = _coverage_issue(organism, assembly)
        if unsupported:
            return ServiceResult.unsupported(
                unsupported, steps=[_done_step(operation, started, heavy=heavy)]
            )
        if self._backend is None:
            return ServiceResult.unsupported(
                f"{operation} requires a GWAS backend; none is configured",
                steps=[_done_step(operation, started, heavy=heavy)],
            )
        try:
            value = invoke()
        except Exception as exc:  # noqa: BLE001
            return ServiceResult.failed(
                RunError(kind="BackendError", message=str(exc)),
                steps=[_failed_step(operation, started, str(exc), heavy=heavy)],
            )

        steps = [_done_step(operation, started, heavy=heavy)]
        if _is_empty(value):
            return ServiceResult.empty(
                "query completed successfully but found no evidence", steps=steps
            )

        finished = utc_now_iso()
        source_release = str(getattr(request, "source_release", "default"))
        evidence = _evidence_for(operation, value, organism, assembly, source_release, finished)
        artifacts = _artifacts_for(operation, value, evidence)
        return ServiceResult.succeeded(value, steps=steps, evidence=evidence, artifacts=artifacts)


def _coverage_issue(organism: str, assembly: str) -> str | None:
    profile = SPECIES_PROFILES.get(organism)
    if profile is None:
        return f"organism {organism!r} is not in the species catalog"
    assembly_info = ASSEMBLY_CATALOG.get(assembly)
    if assembly_info is None or assembly_info.organism != organism:
        return f"assembly {assembly!r} is not catalogued for organism {organism!r}"
    if organism != "Homo sapiens":
        return f"GWAS/QTL resources have limited/no data for organism {organism!r} (GWS-2)"
    return None


def _require_backend(backend: GwasBackend | None) -> GwasBackend:
    assert backend is not None
    return backend


def _is_empty(value: BaseModel) -> bool:
    for field in ("associations", "pairs", "credible_sets", "results"):
        records = getattr(value, field, None)
        if records:
            return False
    return True


def _evidence_for(
    operation: str,
    value: BaseModel,
    organism: str,
    assembly: str,
    source_release: str,
    finished: str,
) -> list[EvidenceItem]:
    confidence = getattr(value, "confidence", None) or Confidence(
        band=ConfidenceBand.MEDIUM,
        basis="statistical evidence supplied by the configured backend",
    )
    associations = getattr(value, "associations", [])
    if associations:
        return [
            EvidenceItem(
                source=association.source,
                source_kind=SourceKind.DATABASE,
                claim=(
                    f"{association.trait} association reported in "
                    f"{association.study_accession}"
                ),
                value={"p_value": association.p_value, "beta": association.beta},
                confidence=confidence,
                provenance=Provenance(
                    tool=association.source,
                    tool_version=association.source_release,
                    inputs={"organism": organism, "assembly": assembly},
                    citations=list(
                        dict.fromkeys([*association.citations, association.study_accession])
                    ),
                    timestamp=finished,
                    output_ref=getattr(value, "storage_ref", None),
                ),
            )
            for association in associations
        ]

    source = getattr(value, "panel", None) or "gwas_backend"
    return [
        EvidenceItem(
            source=source,
            source_kind=SourceKind.DATABASE if operation == "lookup_associations" else SourceKind.COMPUTATION,
            claim=f"GWAS/QTL {operation} produced statistical-genetics evidence",
            confidence=confidence,
            provenance=Provenance(
                tool=operation,
                tool_version=source_release,
                inputs={"organism": organism, "assembly": assembly},
                timestamp=finished,
                output_ref=getattr(value, "storage_ref", None),
            ),
        )
    ]


def _artifacts_for(
    operation: str, value: BaseModel, evidence: list[EvidenceItem]
) -> list[ArtifactRef]:
    artifacts: list[ArtifactRef] = []
    evidence_ids = [item.id for item in evidence]
    storage_ref = getattr(value, "storage_ref", None)
    if storage_ref:
        artifacts.append(
            ArtifactRef(
                type=ArtifactType.FEATURE_TABLE,
                title=f"GWAS/QTL {operation} results",
                storage_ref=storage_ref,
                evidence_ids=evidence_ids,
            )
        )
    locus_plot_ref = getattr(value, "locus_plot_ref", None)
    if locus_plot_ref:
        artifacts.append(
            ArtifactRef(
                type=ArtifactType.LOCUS_PLOT,
                title=f"GWAS/QTL {operation} locus plot",
                storage_ref=locus_plot_ref,
                evidence_ids=evidence_ids,
            )
        )
    return artifacts


def _done_step(name: str, started: str, *, heavy: bool) -> Step:
    return Step(
        name=name,
        tool="gwas_backend",
        weight="heavy" if heavy else "light",
        status=TaskStatus.DONE,
        started_at=started,
        finished_at=utc_now_iso(),
    )


def _failed_step(name: str, started: str, error: str, *, heavy: bool) -> Step:
    return Step(
        name=name,
        tool="gwas_backend",
        weight="heavy" if heavy else "light",
        status=TaskStatus.FAILED,
        started_at=started,
        finished_at=utc_now_iso(),
        error=error,
    )
