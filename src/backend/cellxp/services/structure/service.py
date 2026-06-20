"""Structure service — protein/NA/complex 3D structure, contact maps, DNA shape (X3).

Wraps ESMFold/Boltz-2/Orca/DNAshapeR behind one stable boundary (STS-1..5,
`specs/services/structure_service.md`). A `StructureBackend` is injected for production;
without one every operation returns `ServiceOutcome.UNSUPPORTED` so the agent reports
honestly rather than crashing (same philosophy as N4/N5).

Pure structure prediction is analysis, never actionable; generative design (`design_protein`,
FR-18a) is review-gated and intentionally not implemented here — it lands with X6.
"""

from __future__ import annotations

from cellxp.agent.state import RunError, Step
from cellxp.domain.artifacts import ArtifactRef
from cellxp.domain.clock import utc_now_iso
from cellxp.domain.enums import ArtifactType, SourceKind, TaskStatus
from cellxp.domain.evidence import Confidence, EvidenceItem, Provenance
from cellxp.services.base import Service, ServiceResult
from cellxp.services.registry import registry

from .schemas import (
    ESMFOLD_MAX_RESIDUES,
    ContactMapRequest,
    ContactMapResult,
    DnaShapeRequest,
    DnaShapeResult,
    StructureBackend,
    StructureRequest,
    StructureResult,
)
from .transforms import (
    low_confidence_spans,
    mean_confidence_band,
    select_structure_model,
    validate_kind_alphabet,
)


def _organism_known(organism: str) -> bool:
    from cellxp.services.reference.genome import SPECIES_PROFILES
    return organism in SPECIES_PROFILES


def _assembly_known(assembly: str) -> bool:
    from cellxp.services.reference.genome import ASSEMBLY_CATALOG
    return assembly in ASSEMBLY_CATALOG


@registry.register
class StructureService(Service):
    """Structure-prediction service (ESMFold / Boltz-2 / Orca / DNAshapeR).

    `structure_backend` is the injected inference implementation. Without one, all
    operations return UNSUPPORTED so the agent surfaces a clear "model not configured"
    message instead of raising.
    """

    name = "structure"

    def __init__(self, *, structure_backend: StructureBackend | None = None) -> None:
        self._backend = structure_backend

    # ------------------------------------------------------------------
    # predict_structure (ESMFold / Boltz-2)
    # ------------------------------------------------------------------

    def predict_structure(
        self, request: StructureRequest
    ) -> ServiceResult[StructureResult]:
        """Predict 3D structure for a protein/NA/complex (FR-18, STS-1/3).

        Structure models are sequence-based and organism-agnostic; `organism` is optional
        but, when supplied, must be in the species catalog. Alphabet/length validation runs
        before any (heavy) dispatch.
        """
        started = utc_now_iso()

        if request.organism is not None and not _organism_known(request.organism):
            return ServiceResult.unsupported(
                f"organism {request.organism!r} not in species catalog",
                steps=[_done_step("predict_structure", started)],
            )

        alphabet_error = validate_kind_alphabet(request.kind, request.sequences)
        if alphabet_error is not None:
            return ServiceResult.failed(
                RunError(kind="ValidationError", message=alphabet_error),
                steps=[_failed_step("predict_structure", started, error=alphabet_error)],
            )

        model = select_structure_model(
            request.kind,
            n_chains=len(request.sequences),
            has_ligand=request.ligand is not None,
        )

        # ESMFold has a hard single-sequence length ceiling (`structure_prediction.md` §7).
        if model == "esmfold":
            longest = max((len(s.seq) for s in request.sequences), default=0)
            if longest > ESMFOLD_MAX_RESIDUES:
                msg = (
                    f"sequence length {longest} exceeds ESMFold limit "
                    f"({ESMFOLD_MAX_RESIDUES} residues); use Boltz-2 or a chunking strategy"
                )
                return ServiceResult.failed(
                    RunError(kind="ValidationError", message=msg),
                    steps=[_failed_step("predict_structure", started, error=msg)],
                )

        if self._backend is None:
            return ServiceResult.unsupported(
                f"predict_structure requires a {model!r} backend; none is configured",
                steps=[_done_step("predict_structure", started)],
            )

        try:
            raw = self._backend.predict_structure(request)
        except Exception as exc:  # noqa: BLE001
            return ServiceResult.failed(
                RunError(kind="BackendError", message=str(exc)),
                steps=[_failed_step("predict_structure", started, error=str(exc))],
            )

        finished = utc_now_iso()

        # Service derives confidence band + low-confidence spans from per-residue scores (STS-3).
        per_residue = raw.per_residue_confidence or []
        band = mean_confidence_band(per_residue)
        mean_score = sum(per_residue) / len(per_residue) if per_residue else None
        confidence = Confidence(
            band=band,
            score=mean_score,
            basis="mean per-residue pLDDT-style confidence",
        )
        result = raw.model_copy(
            update={
                "model": raw.model if raw.model != "unknown" else model,
                "confidence": confidence,
                "low_confidence_regions": low_confidence_spans(per_residue),
                "provenance": Provenance(
                    tool=model,
                    tool_version=raw.provenance.tool_version,
                    inputs={
                        "kind": request.kind,
                        "n_chains": len(request.sequences),
                        "has_ligand": request.ligand is not None,
                        "organism": request.organism,
                    },
                    output_ref=raw.structure_ref,
                    timestamp=finished,
                ),
            }
        )

        artifacts: list[ArtifactRef] = []
        if result.structure_ref is not None:
            artifacts.append(
                ArtifactRef(
                    type=ArtifactType.STRUCTURE_3D,
                    title=f"{model} predicted structure",
                    storage_ref=result.structure_ref,
                    summary={
                        "model": result.model,
                        "kind": request.kind,
                        "n_residues": len(per_residue),
                        "affinity": result.affinity,
                        "low_confidence_regions": len(result.low_confidence_regions),
                        "confidence_band": band.value,
                    },
                )
            )

        evidence = [
            EvidenceItem(
                source=model,
                source_kind=SourceKind.MODEL,
                claim=f"{request.kind} structure predicted via {model}",
                confidence=confidence,
                provenance=result.provenance,
            )
        ]
        return ServiceResult.succeeded(
            result,
            steps=[_done_step("predict_structure", started, tool=model, finished=finished,
                              weight="heavy")],
            evidence=evidence,
            artifacts=artifacts,
        )

    # ------------------------------------------------------------------
    # predict_contacts (Orca)
    # ------------------------------------------------------------------

    def predict_contacts(
        self, request: ContactMapRequest
    ) -> ServiceResult[ContactMapResult]:
        """Predict a chromatin contact map over a genomic interval (STS-2)."""
        started = utc_now_iso()

        if not _organism_known(request.organism):
            return ServiceResult.unsupported(
                f"organism {request.organism!r} not in species catalog",
                steps=[_done_step("predict_contacts", started)],
            )
        if not _assembly_known(request.assembly):
            return ServiceResult.unsupported(
                f"assembly {request.assembly!r} not in reference catalog",
                steps=[_done_step("predict_contacts", started)],
            )

        if self._backend is None:
            return ServiceResult.unsupported(
                "predict_contacts requires an Orca contact backend; none is configured",
                steps=[_done_step("predict_contacts", started)],
            )

        try:
            raw = self._backend.predict_contacts(request)
        except Exception as exc:  # noqa: BLE001
            return ServiceResult.failed(
                RunError(kind="BackendError", message=str(exc)),
                steps=[_failed_step("predict_contacts", started, error=str(exc))],
            )

        artifacts: list[ArtifactRef] = []
        if raw.contacts_ref is not None:
            artifacts.append(
                ArtifactRef(
                    type=ArtifactType.CONTACT_MAP,
                    title="predicted chromatin contact map",
                    storage_ref=raw.contacts_ref,
                    summary={
                        "model": raw.model,
                        "chrom": request.interval.chrom,
                        "n_bins": raw.n_bins,
                        "bin_size_bp": raw.bin_size_bp,
                    },
                )
            )
        return ServiceResult.succeeded(
            raw,
            steps=[_done_step("predict_contacts", started, tool=raw.model, weight="heavy")],
            artifacts=artifacts,
        )

    # ------------------------------------------------------------------
    # predict_dna_shape (DNAshapeR)
    # ------------------------------------------------------------------

    def predict_dna_shape(
        self, request: DnaShapeRequest
    ) -> ServiceResult[DnaShapeResult]:
        """Predict a DNA-shape track over a genomic interval (STS-2)."""
        started = utc_now_iso()

        if not _organism_known(request.organism):
            return ServiceResult.unsupported(
                f"organism {request.organism!r} not in species catalog",
                steps=[_done_step("predict_dna_shape", started)],
            )
        if not _assembly_known(request.assembly):
            return ServiceResult.unsupported(
                f"assembly {request.assembly!r} not in reference catalog",
                steps=[_done_step("predict_dna_shape", started)],
            )

        if self._backend is None:
            return ServiceResult.unsupported(
                "predict_dna_shape requires a DNAshapeR backend; none is configured",
                steps=[_done_step("predict_dna_shape", started)],
            )

        try:
            raw = self._backend.predict_dna_shape(request)
        except Exception as exc:  # noqa: BLE001
            return ServiceResult.failed(
                RunError(kind="BackendError", message=str(exc)),
                steps=[_failed_step("predict_dna_shape", started, error=str(exc))],
            )

        artifacts: list[ArtifactRef] = []
        if raw.shape_track_ref is not None:
            artifacts.append(
                ArtifactRef(
                    type=ArtifactType.GENOME_TRACK,
                    title="predicted DNA-shape track",
                    storage_ref=raw.shape_track_ref,
                    summary={
                        "model": raw.model,
                        "chrom": request.interval.chrom,
                        "features": raw.features,
                    },
                )
            )
        return ServiceResult.succeeded(
            raw,
            steps=[_done_step("predict_dna_shape", started, tool=raw.model, weight="heavy")],
            artifacts=artifacts,
        )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _done_step(
    name: str,
    started: str,
    *,
    tool: str = "structure",
    finished: str | None = None,
    weight: str = "light",
) -> Step:
    return Step(
        name=name,
        tool=tool,
        weight=weight,  # type: ignore[arg-type]
        status=TaskStatus.DONE,
        started_at=started,
        finished_at=finished or utc_now_iso(),
    )


def _failed_step(name: str, started: str, *, error: str, tool: str = "structure") -> Step:
    return Step(
        name=name,
        tool=tool,
        weight="light",
        status=TaskStatus.FAILED,
        started_at=started,
        finished_at=utc_now_iso(),
        error=error,
    )
