"""Fail-closed CRISPR scoring and genome-wide off-target worker."""

from __future__ import annotations

from fastapi import FastAPI, HTTPException

from .backends import DeterministicCrisprBackend
from .schemas import (
    CrisprRequest,
    CrisprResult,
    EditOutcomeRequest,
    EditOutcomeResult,
    GuideScoringRequest,
    GuideScoringResult,
    OffTargetRequest,
    OffTargetResult,
)
from .worker_contract import (
    assembly_index,
    fixture_mode,
    index_manifest,
    manifest_sha256,
    packaged_worker_manifest,
    production_backend,
)

app = FastAPI(title="CellXP CRISPR worker", version="1")
_fixture = DeterministicCrisprBackend()


@app.get("/health")
def health() -> dict[str, object]:
    source_manifest = packaged_worker_manifest()
    indexes = index_manifest()
    if fixture_mode():
        return {
            "status": "ok",
            "mode": "contract_fixture",
            "algorithms": ["sequence_qc_contract_fixture"],
            "worker_revision": source_manifest.worker_revision,
            "source_manifest_sha256": manifest_sha256(source_manifest),
            "index_manifest_sha256": manifest_sha256(indexes),
            "assemblies": [item.assembly for item in indexes.indexes],
        }
    backend = production_backend()
    runtime = backend.attest()
    return {
        "status": "ok",
        "mode": "production",
        "algorithms": runtime.get("algorithms", []),
        "source_revisions": runtime["source_revisions"],
        "worker_revision": source_manifest.worker_revision,
        "source_manifest_sha256": manifest_sha256(source_manifest),
        "index_manifest_sha256": manifest_sha256(indexes),
        "assemblies": [item.assembly for item in indexes.indexes],
    }


@app.get("/version")
def version() -> dict[str, object]:
    return packaged_worker_manifest().model_dump(mode="json")


@app.post("/v1/design-guides", response_model=CrisprResult)
def design_guides(request: CrisprRequest) -> CrisprResult:
    index = assembly_index(request.organism, request.assembly)
    if fixture_mode():
        result = _fixture.design_guides(request)
        return result.model_copy(update={
            "rationale": (
                "contract fixture only; no candidates or genome search performed; "
                f"assembly topology={index.topology}"
            )
        })
    return production_backend().design_guides(request, assembly_index=index)


@app.post("/v1/off-targets", response_model=OffTargetResult)
def enumerate_off_targets(request: OffTargetRequest) -> OffTargetResult:
    index = assembly_index(request.organism, request.assembly)
    if fixture_mode():
        return _fixture.enumerate_off_targets(request)
    return production_backend().enumerate_off_targets(request, assembly_index=index)


@app.post("/v1/on-target-scores", response_model=GuideScoringResult)
def score_on_target(request: GuideScoringRequest) -> GuideScoringResult:
    index = assembly_index(request.organism, request.assembly)
    if fixture_mode():
        if request.model not in {"auto", "contract_fixture_qc"}:
            raise HTTPException(
                status_code=422,
                detail="contract fixture cannot claim Rule Set 2 or another production scorer",
            )
        return _fixture.score_on_target(request)
    return production_backend().score_on_target(request, assembly_index=index)


@app.post("/v1/edit-outcomes", response_model=EditOutcomeResult)
def predict_edit_outcomes(request: EditOutcomeRequest) -> EditOutcomeResult:
    index = assembly_index(request.organism, request.assembly)
    if fixture_mode():
        return _fixture.predict_edit_outcomes(request)
    return production_backend().predict_edit_outcomes(request, assembly_index=index)
