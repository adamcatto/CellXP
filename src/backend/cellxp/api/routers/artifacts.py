from threading import RLock

import json

from fastapi import APIRouter, HTTPException, Response, status

from cellxp.api.runtime import runtime
from cellxp.api.schemas import (
    ArtifactExportRequest,
    ArtifactExportResponse,
    ArtifactManifestResponse,
    GuidePoolResponse,
    SaveGuidePoolRequest,
)
from cellxp.config.settings import Settings
from cellxp.domain.clock import utc_now_iso
from cellxp.domain.ids import new_id
from cellxp.storage.guide_pool_repository import GuidePoolConflictError, GuidePoolRepository
from cellxp.storage.object_store import content_hash, object_store_from_url

router = APIRouter(prefix="/artifacts", tags=["artifacts"])

@router.get("")
def index():
    return {"status": "ok", "router": "artifacts"}


def _artifact(artifact_id: str) -> tuple[dict[str, object], dict[str, object]]:
    return runtime.find_artifact(artifact_id)


@router.get("/{artifact_id}", response_model=ArtifactManifestResponse)
def get_artifact(artifact_id: str) -> ArtifactManifestResponse:
    snapshot, artifact = _artifact(artifact_id)
    return ArtifactManifestResponse.model_validate({
        **artifact,
        "session_id": snapshot["session_id"],
        "run_id": snapshot["id"],
        "schema_version": "1.0",
        "payload_schema": f"cellxp.{artifact['type']}/1.0",
        "content_available": bool(artifact.get("storage_ref") or artifact.get("summary")),
        # Object-store keys are deliberately excluded from the HTTP representation (API-3).
        "storage_ref": None,
    })


@router.get("/{artifact_id}/content")
def get_artifact_content(artifact_id: str) -> Response:
    _, artifact = _artifact(artifact_id)
    media_type = str(artifact.get("content_type") or "application/json")
    if storage_ref := artifact.get("storage_ref"):
        try:
            data = object_store_from_url(Settings().object_store_url).get(str(storage_ref))
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="artifact content not found") from exc
    else:
        data = json.dumps(artifact.get("summary", {}), sort_keys=True).encode()
    return Response(
        content=data, media_type=media_type,
        headers={"ETag": content_hash(data), "Content-Disposition": "inline"},
    )


@router.post(
    "/{artifact_id}/exports", response_model=ArtifactExportResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_artifact_export(
    artifact_id: str, request: ArtifactExportRequest
) -> ArtifactExportResponse:
    snapshot, artifact = _artifact(artifact_id)
    if artifact.get("actionable") and artifact.get("review_status") != "approved":
        raise HTTPException(
            status_code=409, detail="actionable artifact requires approval before export"
        )
    if request.format not in {"json", "raw"}:
        raise HTTPException(status_code=422, detail="unsupported export format")
    media_type = str(artifact.get("content_type") or "application/json")
    if storage_ref := artifact.get("storage_ref"):
        try:
            data = object_store_from_url(Settings().object_store_url).get(str(storage_ref))
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="artifact content not found") from exc
    else:
        data = json.dumps(artifact.get("summary", {}), sort_keys=True).encode()
    stored = object_store_from_url(Settings().object_store_url).put(data, content_type=media_type)
    descriptor = ArtifactExportResponse(
        id=new_id(), artifact_id=artifact_id, format=request.format,
        media_type=media_type, content_hash=stored.hash,
    )
    runtime.record_export(artifact_id, descriptor.model_dump(mode="json"))
    runtime.audit_export(
        str(snapshot["id"]), artifact_id,
        {
            "export_id": descriptor.id, "format": request.format,
            "content_hash": descriptor.content_hash,
            "review_status": artifact.get("review_status"),
        },
    )
    return descriptor


_lock = RLock()
_local_pools: dict[str, GuidePoolResponse] = {}


def _repository() -> GuidePoolRepository | None:
    factory = getattr(runtime, "_factory", None)
    return GuidePoolRepository(factory) if factory is not None else None


@router.get("/{artifact_id}/guide-pools")
def list_guide_pools(artifact_id: str) -> dict[str, object]:
    repository = _repository()
    if repository is not None:
        items = repository.list_for_artifact(artifact_id)
    else:
        with _lock:
            items = [item for item in _local_pools.values() if item.source_artifact_id == artifact_id]
    return {"items": items, "next_cursor": None}


@router.post(
    "/{artifact_id}/guide-pools", response_model=GuidePoolResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_guide_pool(artifact_id: str, request: SaveGuidePoolRequest) -> GuidePoolResponse:
    runtime.get_session(request.session_id)
    repository = _repository()
    if repository is not None:
        return repository.save(artifact_id, request)
    now = utc_now_iso()
    item = GuidePoolResponse(
        id=new_id(), session_id=request.session_id, source_artifact_id=artifact_id,
        name=request.name, guide_ids=request.guide_ids, revision=0,
        created_at=now, updated_at=now,
    )
    with _lock:
        _local_pools[item.id] = item
    return item


@router.put("/{artifact_id}/guide-pools/{pool_id}", response_model=GuidePoolResponse)
def update_guide_pool(
    artifact_id: str, pool_id: str, request: SaveGuidePoolRequest
) -> GuidePoolResponse:
    runtime.get_session(request.session_id)
    repository = _repository()
    try:
        if repository is not None:
            existing = repository.get(pool_id)
            if existing is None:
                raise HTTPException(status_code=404, detail="guide pool not found")
            return repository.save(artifact_id, request, pool_id=pool_id)
        with _lock:
            existing = _local_pools.get(pool_id)
            if existing is None:
                raise HTTPException(status_code=404, detail="guide pool not found")
            if existing.source_artifact_id != artifact_id or request.expected_revision != existing.revision:
                raise GuidePoolConflictError("guide pool revision conflict")
            updated = existing.model_copy(update={
                "name": request.name, "guide_ids": request.guide_ids,
                "revision": existing.revision + 1, "updated_at": utc_now_iso(),
            })
            _local_pools[pool_id] = updated
            return updated
    except GuidePoolConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
