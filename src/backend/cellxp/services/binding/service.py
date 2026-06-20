"""Binding service — motif scanning, TF occupancy, and variant binding-delta (N5).

Implements BIS-1..5 (`specs/services/binding_service.md`). Organism routing is enforced:
AlphaGenome/ChromBPNet binding heads are mammalian-only; other clades use motif scanning
+ Evo 2 priors. When no backend is configured, operations return UNSUPPORTED; empty
motif/binding results use ServiceOutcome.EMPTY rather than FAILURE (BIS-5).
"""

from __future__ import annotations

from cellxp.agent.state import RunError, Step
from cellxp.domain.clock import utc_now_iso
from cellxp.domain.enums import ConfidenceBand, OrganismClass, SourceKind, TaskStatus
from cellxp.domain.evidence import Confidence, EvidenceItem, Provenance
from cellxp.services.base import Service, ServiceResult
from cellxp.services.registry import registry

from .delta import BindingDeltaRequest, BindingDeltaResult, BindingRequest, BindingResult
from .motifs import MotifScanRequest, MotifScanResult

_MAMMALIAN = frozenset({OrganismClass.MAMMALIAN})


def _organism_class(organism: str) -> OrganismClass | None:
    from cellxp.services.reference.genome import SPECIES_PROFILES
    profile = SPECIES_PROFILES.get(organism)
    return profile.organism_class if profile else None


@registry.register
class BindingService(Service):
    """TF binding prediction and motif-scan service (BIS-1..5).

    An injectable `binding_backend` handles heavy model inference (AlphaGenome binding
    heads, ChromBPNet). Without one, motif-scan results can still be returned if a
    `motif_backend` is provided; otherwise all operations return UNSUPPORTED.
    """

    name = "binding"

    def __init__(
        self,
        *,
        binding_backend=None,
        motif_backend=None,
    ) -> None:
        self._binding_backend = binding_backend
        self._motif_backend = motif_backend

    # ------------------------------------------------------------------
    # scan_motifs
    # ------------------------------------------------------------------

    def scan_motifs(self, request: MotifScanRequest) -> ServiceResult[MotifScanResult]:
        """Scan a sequence or interval for TF motif hits (BIS-1/5)."""
        started = utc_now_iso()

        if self._motif_backend is None:
            return ServiceResult.unsupported(
                "scan_motifs requires a motif backend (FIMO + JASPAR); none is configured",
                steps=[_done_step("scan_motifs", started)],
            )

        try:
            raw = self._motif_backend.scan(request)
        except Exception as exc:  # noqa: BLE001
            return ServiceResult.failed(
                RunError(kind="BackendError", message=str(exc)),
                steps=[_failed_step("scan_motifs", started, error=str(exc))],
            )

        if not raw.hits:
            return ServiceResult.empty(
                "no motif hits detected in the submitted sequence (BIS-5)",
                steps=[_done_step("scan_motifs", started)],
            )

        return ServiceResult.succeeded(
            raw,
            steps=[_done_step("scan_motifs", started)],
            evidence=[
                EvidenceItem(
                    source=f"{raw.motif_db}_{raw.motif_db_release}",
                    source_kind=SourceKind.DATABASE,
                    claim=f"Found {len(raw.hits)} motif hit(s) via {raw.motif_db}",
                    confidence=Confidence(band=ConfidenceBand.MEDIUM),
                    provenance=Provenance(
                        tool="FIMO",
                        inputs={"motif_db": raw.motif_db, "motif_db_release": raw.motif_db_release},
                    ),
                )
            ],
        )

    # ------------------------------------------------------------------
    # predict_binding
    # ------------------------------------------------------------------

    def predict_binding(self, request: BindingRequest) -> ServiceResult[BindingResult]:
        """Predict TF binding and accessibility; compute delta if variant present."""
        started = utc_now_iso()

        cls = _organism_class(request.organism)
        if cls is None:
            return ServiceResult.unsupported(
                f"organism {request.organism!r} not in species catalog",
                steps=[_done_step("predict_binding", started)],
            )

        if cls not in _MAMMALIAN and self._binding_backend is None:
            return ServiceResult.unsupported(
                f"binding prediction for non-mammalian organisms requires an Evo 2 backend; "
                f"none is configured ({request.organism!r} is {cls.value})",
                steps=[_done_step("predict_binding", started)],
            )

        if self._binding_backend is None:
            return ServiceResult.unsupported(
                "predict_binding requires a binding backend (AlphaGenome/ChromBPNet); "
                "none is configured",
                steps=[_done_step("predict_binding", started)],
            )

        try:
            raw = self._binding_backend.predict(request)
        except Exception as exc:  # noqa: BLE001
            return ServiceResult.failed(
                RunError(kind="BackendError", message=str(exc)),
                steps=[_failed_step("predict_binding", started, error=str(exc))],
            )

        return ServiceResult.succeeded(
            raw,
            steps=[_done_step("predict_binding", started)],
        )

    # ------------------------------------------------------------------
    # score_binding_delta (N5 — variant binding evidence)
    # ------------------------------------------------------------------

    def score_binding_delta(
        self, request: BindingDeltaRequest
    ) -> ServiceResult[BindingDeltaResult]:
        """Score variant-induced occupancy changes for TF binding sites (BIS-3).

        Mammalian organisms use AlphaGenome binding heads; all clades fall back to
        FIMO motif scanning + delta classification when only a motif backend is present.
        """
        started = utc_now_iso()

        cls = _organism_class(request.organism)
        if cls is None:
            return ServiceResult.unsupported(
                f"organism {request.organism!r} not in species catalog",
                steps=[_done_step("score_binding_delta", started)],
            )

        # With neither backend configured, return unsupported.
        if self._binding_backend is None and self._motif_backend is None:
            return ServiceResult.unsupported(
                "score_binding_delta requires a binding or motif backend; none is configured",
                steps=[_done_step("score_binding_delta", started)],
            )

        if self._binding_backend is not None:
            try:
                raw = self._binding_backend.score_delta(request)
            except Exception as exc:  # noqa: BLE001
                return ServiceResult.failed(
                    RunError(kind="BackendError", message=str(exc)),
                    steps=[_failed_step("score_binding_delta", started, error=str(exc))],
                )
            return ServiceResult.succeeded(
                raw,
                steps=[_done_step("score_binding_delta", started)],
                evidence=[
                    EvidenceItem(
                        source="alphagenome_binding",
                        source_kind=SourceKind.MODEL,
                        claim=(
                            f"Binding delta for {request.variant.chrom}:{request.variant.pos}"
                            f" computed via AlphaGenome binding heads"
                        ),
                        confidence=Confidence(band=ConfidenceBand.MEDIUM),
                        provenance=Provenance(
                            tool="alphagenome_binding",
                            tool_version="unknown",
                            inputs={
                                "organism": request.organism,
                                "assembly": request.assembly,
                            },
                        ),
                    )
                ],
            )

        # Motif-only path: unsupported for quantitative delta but record evidence of attempt.
        return ServiceResult.unsupported(
            "quantitative binding-delta requires a model backend; "
            "motif-scan-only mode does not produce occupancy values",
            steps=[_done_step("score_binding_delta", started)],
        )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _done_step(name: str, started: str) -> Step:
    return Step(
        name=name,
        tool="binding",
        weight="light",
        status=TaskStatus.DONE,
        started_at=started,
        finished_at=utc_now_iso(),
    )


def _failed_step(name: str, started: str, *, error: str) -> Step:
    return Step(
        name=name,
        tool="binding",
        weight="light",
        status=TaskStatus.FAILED,
        started_at=started,
        finished_at=utc_now_iso(),
        error=error,
    )
