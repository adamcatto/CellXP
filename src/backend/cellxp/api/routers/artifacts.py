from threading import RLock

from fastapi import APIRouter, HTTPException, status

from cellxp.api.runtime import runtime
from cellxp.api.schemas import GuidePoolResponse, SaveGuidePoolRequest
from cellxp.domain.clock import utc_now_iso
from cellxp.domain.ids import new_id
from cellxp.storage.guide_pool_repository import GuidePoolConflictError, GuidePoolRepository

router = APIRouter(prefix="/artifacts", tags=["artifacts"])

@router.get("")
def index():
    return {"status": "ok", "router": "artifacts"}


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
