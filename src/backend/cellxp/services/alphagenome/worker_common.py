"""Shared fail-closed contracts for sequence-model workers."""

from __future__ import annotations

import hashlib
import importlib
import json
import os
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal

from fastapi import HTTPException
from pydantic import BaseModel

from .schemas import alphagenome_applicable, organism_class_for


class WeightArtifact(BaseModel):
    filename: str
    url: str
    sha256: str
    size_bytes: int | None = None


class WorkerManifest(BaseModel):
    schema_version: Literal["1.0"]
    model: Literal["alphagenome", "evo2"]
    model_revision: str
    runtime_revision: str
    dependencies: dict[str, str]
    weights: list[WeightArtifact]
    distribution: str


def load_manifest(name: str) -> WorkerManifest:
    path = Path(__file__).with_name("model_manifests") / f"{name}.json"
    return WorkerManifest.model_validate_json(path.read_text(encoding="utf-8"))


def manifest_digest(manifest: WorkerManifest) -> str:
    payload = json.dumps(manifest.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode()).hexdigest()


def enforce_model_organism(model: str, organism: str) -> None:
    organism_class = organism_class_for(organism)
    if organism_class is None:
        raise HTTPException(status_code=422, detail=f"unknown organism {organism!r}")
    if model == "alphagenome" and not alphagenome_applicable(organism):
        raise HTTPException(
            status_code=422,
            detail=f"AlphaGenome supports catalogued mammalian organisms only; got {organism!r}",
        )


@lru_cache(maxsize=2)
def production_backend(model: str) -> Any:
    """Load the packaged pinned SDK adapter, with an explicit operator override seam."""
    defaults = {
        "alphagenome": "cellxp.services.alphagenome.sdk_backends:create_alphagenome_backend",
        "evo2": "cellxp.services.alphagenome.sdk_backends:create_evo2_backend",
    }
    setting = os.getenv(f"CELLXP_{model.upper()}_RUNTIME_FACTORY", defaults[model]).strip()
    if not setting or ":" not in setting:
        raise HTTPException(
            status_code=503,
            detail=f"CELLXP_{model.upper()}_RUNTIME_FACTORY=module:function is required",
        )
    module_name, function_name = setting.split(":", 1)
    try:
        verify_local_artifacts(load_manifest(model))
        factory = getattr(importlib.import_module(module_name), function_name)
        return factory(load_manifest(model))
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=503, detail=f"{model} runtime failed to load: {exc}") from exc


def fixture_mode() -> bool:
    return os.getenv("CELLXP_SEQUENCE_WORKER_MODE", "production") == "fixture"


def call_production(model: str, operation: str, request: Any) -> Any:
    """Invoke one packaged operation with stable fail-closed HTTP errors."""
    try:
        return getattr(production_backend(model), operation)(request)
    except HTTPException:
        raise
    except (ValueError, NotImplementedError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=503, detail=f"{model} inference failed: {exc}") from exc


def verify_local_artifacts(manifest: WorkerManifest) -> None:
    root = Path(os.getenv("MODEL_CACHE_DIR", "/models"))
    for artifact in manifest.weights:
        path = root / artifact.filename
        if not path.is_file():
            raise ValueError(f"missing pinned artifact {path}")
        checksum = hashlib.sha256()
        with path.open("rb") as stream:
            while chunk := stream.read(1024 * 1024):
                checksum.update(chunk)
        if checksum.hexdigest() != artifact.sha256:
            raise ValueError(f"checksum mismatch for pinned artifact {path}")


def health_payload(manifest: WorkerManifest) -> dict[str, Any]:
    mode = os.getenv("CELLXP_SEQUENCE_WORKER_MODE", "production")
    defaults = {
        "alphagenome": "cellxp.services.alphagenome.sdk_backends:create_alphagenome_backend",
        "evo2": "cellxp.services.alphagenome.sdk_backends:create_evo2_backend",
    }
    factory = os.getenv(
        f"CELLXP_{manifest.model.upper()}_RUNTIME_FACTORY", defaults[manifest.model]
    ).strip()
    ready = bool(factory)
    reason = None
    if mode != "fixture":
        try:
            if manifest.model == "alphagenome" and not os.getenv("ALPHAGENOME_API_KEY", "").strip():
                raise ValueError("ALPHAGENOME_API_KEY is required")
            verify_local_artifacts(manifest)
        except ValueError as exc:
            ready = False
            reason = str(exc)
    return {
        "status": "ok" if mode == "fixture" or ready else "not_ready",
        "mode": mode,
        "model": manifest.model,
        "model_revision": manifest.model_revision,
        "runtime_revision": manifest.runtime_revision,
        "manifest_sha256": manifest_digest(manifest),
        "reason": reason,
    }
