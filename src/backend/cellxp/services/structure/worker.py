"""ASGI entry point for the isolated, warm-loaded structure GPU worker."""

from __future__ import annotations

import os
from functools import lru_cache

from fastapi import FastAPI, HTTPException

from cellxp.storage.object_store import object_store_from_url

from .backends import ProductionStructureBackend, StructureRuntimeConfig
from .schemas import StructureRequest, StructureResult

app = FastAPI(title="CellXP structure worker", version="1")


@lru_cache(maxsize=1)
def get_backend() -> ProductionStructureBackend:
    config = StructureRuntimeConfig.from_env()
    store = object_store_from_url(os.getenv("OBJECT_STORE_URL", "file:///tmp/cellxp-artifacts"))
    return ProductionStructureBackend(object_store=store, config=config)


@app.get("/health")
def health() -> dict[str, str]:
    config = StructureRuntimeConfig.from_env()
    return {
        "status": "ok",
        "device": config.device,
        "esmfold_revision": config.esmfold_revision,
    }


@app.post("/v1/predict", response_model=StructureResult)
def predict(request: StructureRequest) -> StructureResult:
    try:
        return get_backend().predict_structure(request)
    except (RuntimeError, ValueError) as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
