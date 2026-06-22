"""ASGI entry point for the independently deployed GWAS statistical worker."""

from __future__ import annotations

import os
from functools import lru_cache

from fastapi import FastAPI, HTTPException

from cellxp.storage.object_store import object_store_from_url

from .schemas import (
    ColocBatchResult, ColocRequest, FineMapRequest, FineMapResult, GwasRequest, GwasResult,
    LdRequest, LdResult,
)
from .worker_backend import (
    ExternalStatisticalEngine, GWAS_WORKER_REVISION, GwasWorkerBackend, GwasWorkerConfig,
)

app = FastAPI(title="CellXP GWAS statistical worker", version=GWAS_WORKER_REVISION)


@lru_cache(maxsize=1)
def get_backend() -> GwasWorkerBackend:
    config = GwasWorkerConfig.from_env()
    store = object_store_from_url(os.getenv("OBJECT_STORE_URL", "file:///tmp/cellxp-artifacts"))
    return GwasWorkerBackend(ExternalStatisticalEngine(store, config), store)


@app.get("/health")
def health() -> dict[str, str]:
    config = GwasWorkerConfig.from_env()
    return {"status": "ok", "revision": config.expected_revision}


@app.get("/ready")
def ready() -> dict[str, str]:
    try:
        engine = get_backend().engine
        if not isinstance(engine, ExternalStatisticalEngine):
            raise RuntimeError("production worker requires ExternalStatisticalEngine")
        return engine.readiness()
    except (RuntimeError, ValueError) as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


def _execute(call):  # noqa: ANN001, ANN202
    try:
        return call()
    except (RuntimeError, ValueError, KeyError) as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.post("/v1/ld", response_model=LdResult)
def compute_ld(request: LdRequest) -> LdResult:
    return _execute(lambda: get_backend().compute_ld(request))


@app.post("/v1/associations", response_model=GwasResult)
def associations(request: GwasRequest) -> GwasResult:
    return get_backend().lookup_associations(request)


@app.post("/v1/fine-map", response_model=FineMapResult)
def fine_map(request: FineMapRequest) -> FineMapResult:
    return _execute(lambda: get_backend().fine_map(request))


@app.post("/v1/coloc", response_model=ColocBatchResult)
def coloc(request: ColocRequest) -> ColocBatchResult:
    return _execute(lambda: get_backend().coloc(request))
