"""Version and reference-index attestations for the isolated CRISPR worker."""

from __future__ import annotations

import hashlib
import importlib
import json
import os
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal

from fastapi import HTTPException
from pydantic import BaseModel, Field


class UpstreamSource(BaseModel):
    name: str
    version: str
    revision: str
    archive_url: str
    archive_sha256: str


class CrisprWorkerManifest(BaseModel):
    schema_version: Literal["1.0"]
    worker_revision: str
    sources: list[UpstreamSource]


class IndexFile(BaseModel):
    path: str
    sha256: str
    role: Literal["reference_fasta", "off_target_index", "auxiliary"] = "auxiliary"


class AssemblyIndex(BaseModel):
    organism: str
    assembly: str
    topology: Literal["linear", "circular"]
    files: list[IndexFile] = Field(default_factory=list)
    contig_lengths: dict[str, int] = Field(default_factory=dict)


class IndexManifest(BaseModel):
    schema_version: Literal["1.0"]
    fixture: bool = False
    indexes: list[AssemblyIndex]


def packaged_worker_manifest() -> CrisprWorkerManifest:
    path = Path(__file__).with_name("worker_manifest.json")
    return CrisprWorkerManifest.model_validate_json(path.read_text(encoding="utf-8"))


def manifest_sha256(value: BaseModel) -> str:
    payload = json.dumps(value.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode()).hexdigest()


@lru_cache(maxsize=1)
def index_manifest() -> IndexManifest:
    if fixture_mode():
        path = Path(__file__).with_name("fixture_index_manifest.json")
    else:
        configured = os.getenv("CRISPR_INDEX_MANIFEST", "").strip()
        if not configured:
            raise HTTPException(status_code=503, detail="CRISPR_INDEX_MANIFEST is required")
        path = Path(configured)
    try:
        manifest = IndexManifest.model_validate_json(path.read_text(encoding="utf-8"))
        if not fixture_mode():
            verify_index_files(manifest, path.parent)
        return manifest
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=503, detail=f"invalid CRISPR index manifest: {exc}") from exc


def verify_index_files(manifest: IndexManifest, root: Path) -> None:
    if manifest.fixture:
        raise ValueError("fixture index manifest is forbidden in production")
    if not manifest.indexes:
        raise ValueError("at least one assembly index is required")
    for index in manifest.indexes:
        if not index.files:
            raise ValueError(f"assembly {index.assembly} has no attested index files")
        for item in index.files:
            path = root / item.path
            if not path.is_file():
                raise ValueError(f"missing index artifact {path}")
            if file_sha256(path) != item.sha256:
                raise ValueError(f"checksum mismatch for index artifact {path}")


def assembly_index(organism: str, assembly: str) -> AssemblyIndex:
    for item in index_manifest().indexes:
        if item.organism == organism and item.assembly == assembly:
            return item
    raise HTTPException(
        status_code=422,
        detail=f"no attested off-target index for {organism!r} assembly {assembly!r}",
    )


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def fixture_mode() -> bool:
    return os.getenv("CELLXP_CRISPR_WORKER_MODE", "production") == "contract_fixture"


@lru_cache(maxsize=1)
def production_backend() -> Any:
    setting = os.getenv("CELLXP_CRISPR_RUNTIME_FACTORY", "").strip()
    if not setting or ":" not in setting:
        raise HTTPException(
            status_code=503,
            detail="CELLXP_CRISPR_RUNTIME_FACTORY=module:function is required",
        )
    module_name, function_name = setting.split(":", 1)
    manifest = packaged_worker_manifest()
    indexes = index_manifest()
    try:
        factory = getattr(importlib.import_module(module_name), function_name)
        backend = factory(manifest, indexes)
        attestation = backend.attest()
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=503, detail=f"CRISPR runtime failed to load: {exc}") from exc
    expected = {source.name: source.revision for source in manifest.sources}
    if attestation.get("source_revisions") != expected:
        raise HTTPException(status_code=503, detail="CRISPR runtime source revisions do not attest")
    return backend
