"""Pinned statistical worker implementation for LD, SuSiE, and coloc.

External executors are isolated behind ``StatisticalEngine``. Production mode invokes pinned
PLINK/R entry points and fails closed when a binary, panel, or required input is unavailable.
Tests inject a deterministic engine; that engine is never selected by production defaults.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from cellxp.domain.enums import ConfidenceBand
from cellxp.domain.evidence import Confidence, Provenance
from cellxp.storage.object_store import ObjectStore

from .schemas import (
    ColocBatchResult, ColocRequest, FineMapRequest, FineMapResult, GwasRequest, GwasResult,
    LdRequest, LdResult,
)

PLINK_VERSION = "2.00a6.9"
SUSIER_VERSION = "0.12.35"
COLOC_VERSION = "5.2.3"
GWAS_WORKER_REVISION = (
    f"plink@{PLINK_VERSION}+susieR@{SUSIER_VERSION}+coloc@{COLOC_VERSION}"
)


class StatisticalEngine(Protocol):
    revision: str

    def compute_ld(self, request: LdRequest) -> LdResult: ...
    def fine_map(self, request: FineMapRequest) -> FineMapResult: ...
    def coloc(self, request: ColocRequest) -> ColocBatchResult: ...


@dataclass(frozen=True)
class GwasWorkerConfig:
    plink_executable: str = "plink2"
    rscript_executable: str = "Rscript"
    panel_manifest: Path = Path("/data/ld-panels/manifest.json")
    script_dir: Path = Path("/opt/cellxp/gwas")
    timeout_seconds: int = 1800
    expected_revision: str = GWAS_WORKER_REVISION

    @classmethod
    def from_env(cls) -> "GwasWorkerConfig":
        timeout = int(os.getenv("GWAS_WORKER_TIMEOUT_SECONDS", "1800"))
        if timeout < 1:
            raise ValueError("GWAS_WORKER_TIMEOUT_SECONDS must be positive")
        revision = os.getenv("GWAS_WORKER_REVISION", GWAS_WORKER_REVISION)
        if revision != GWAS_WORKER_REVISION:
            raise RuntimeError(
                f"GWAS_WORKER_REVISION drift: expected {GWAS_WORKER_REVISION}, got {revision}"
            )
        return cls(
            plink_executable=os.getenv("PLINK_EXECUTABLE", "plink2"),
            rscript_executable=os.getenv("RSCRIPT_EXECUTABLE", "Rscript"),
            panel_manifest=Path(os.getenv("GWAS_LD_PANEL_MANIFEST", "/data/ld-panels/manifest.json")),
            script_dir=Path(os.getenv("GWAS_SCRIPT_DIR", "/opt/cellxp/gwas")),
            timeout_seconds=timeout,
            expected_revision=revision,
        )


class ExternalStatisticalEngine:
    """Run release-pinned command-line tools without a shell."""

    revision = GWAS_WORKER_REVISION

    def __init__(self, store: ObjectStore, config: GwasWorkerConfig) -> None:
        self.store = store
        self.config = config

    def readiness(self) -> dict[str, str]:
        missing = [
            name for name in (self.config.plink_executable, self.config.rscript_executable)
            if shutil.which(name) is None
        ]
        if missing:
            raise RuntimeError(f"missing statistical executables: {', '.join(missing)}")
        if not self.config.panel_manifest.is_file():
            raise RuntimeError(f"LD panel manifest not found: {self.config.panel_manifest}")
        for script in ("run_susie.R", "run_coloc.R"):
            if not (self.config.script_dir / script).is_file():
                raise RuntimeError(f"statistical worker script not found: {script}")
        plink_version = self._capture([self.config.plink_executable, "--version"])
        if PLINK_VERSION not in plink_version:
            raise RuntimeError(f"PLINK version drift: expected {PLINK_VERSION}")
        r_versions = self._capture([
            self.config.rscript_executable, "-e",
            "cat(as.character(packageVersion('susieR')), '+', "
            "as.character(packageVersion('coloc')), sep='')",
        ])
        if r_versions.strip() != f"{SUSIER_VERSION}+{COLOC_VERSION}":
            raise RuntimeError(
                f"R package version drift: expected {SUSIER_VERSION}+{COLOC_VERSION}, "
                f"got {r_versions.strip()}"
            )
        return {"status": "ready", "revision": self.revision}

    def compute_ld(self, request: LdRequest) -> LdResult:
        manifest = json.loads(self.config.panel_manifest.read_text(encoding="utf-8"))
        key = f"{request.assembly}:{request.population}"
        panel = manifest.get("panels", {}).get(key)
        if not panel:
            raise ValueError(f"no ancestry-matched LD panel for {key}")
        prefix = str(panel["pfile_prefix"])
        chrom = request.interval.chrom.removeprefix("chr")
        with tempfile.TemporaryDirectory(prefix="cellxp-ld-") as tmp:
            output = Path(tmp) / "ld"
            argv = [
                self.config.plink_executable, "--pfile", prefix, "--chr", chrom,
                "--from-bp", str(request.interval.start + 1), "--to-bp", str(request.interval.end),
                "--r2-phased", "square0", "--out", str(output),
            ]
            self._run(argv)
            ids_path, matrix_path = output.with_suffix(".vcor1.vars"), output.with_suffix(".vcor1")
            if not ids_path.is_file() or not matrix_path.is_file():
                raise RuntimeError("PLINK did not produce the expected LD matrix outputs")
            ids = [line.strip() for line in ids_path.read_text().splitlines() if line.strip()]
            rows = [[float(value) for value in line.split()] for line in matrix_path.read_text().splitlines()]
        from .schemas import LdPair
        pairs = [
            LdPair(variant_a=ids[i], variant_b=ids[j], r2=value)
            for i, row in enumerate(rows) for j, value in enumerate(row) if j > i
        ]
        return LdResult(
            pairs=pairs,
            population=request.population,
            panel=str(panel["id"]),
            assumptions=["ancestry-matched panel", "biallelic variants", "phased LD"],
            provenance=Provenance(
                tool="PLINK2", tool_version=PLINK_VERSION,
                inputs={"panel": panel["id"], "panel_sha256": panel["sha256"]},
            ),
        )

    def fine_map(self, request: FineMapRequest) -> FineMapResult:
        if not request.ld_matrix_ref:
            raise ValueError("SuSiE requires ld_matrix_ref; identity LD is not permitted")
        with tempfile.TemporaryDirectory(prefix="cellxp-susie-") as tmp:
            root = Path(tmp)
            stats = self._materialize(request.summary_stats_ref, root / "summary.tsv")
            ld = self._materialize(request.ld_matrix_ref, root / "ld.tsv")
            output = root / "result.json"
            self._run([
                self.config.rscript_executable, str(self.config.script_dir / "run_susie.R"),
                str(stats), str(ld), str(output), request.interval.chrom,
                str(request.interval.start), str(request.interval.end), request.assembly,
            ])
            result = FineMapResult.model_validate_json(output.read_text(encoding="utf-8"))
        return result.model_copy(update={"provenance": Provenance(
            tool="susieR", tool_version=SUSIER_VERSION,
            inputs={"summary_stats_ref": request.summary_stats_ref,
                    "ld_matrix_ref": request.ld_matrix_ref},
        )})

    def coloc(self, request: ColocRequest) -> ColocBatchResult:
        with tempfile.TemporaryDirectory(prefix="cellxp-coloc-") as tmp:
            root = Path(tmp)
            gwas = self._materialize(request.gwas_stats_ref, root / "gwas.tsv")
            qtl = self._materialize(request.qtl_stats_ref, root / "qtl.tsv")
            output = root / "result.json"
            self._run([
                self.config.rscript_executable, str(self.config.script_dir / "run_coloc.R"),
                str(gwas), str(qtl), str(output), request.trait,
                ",".join(request.tissues),
            ])
            result = ColocBatchResult.model_validate_json(output.read_text(encoding="utf-8"))
        return result.model_copy(update={"provenance": Provenance(
            tool="coloc", tool_version=COLOC_VERSION,
            inputs={"gwas_stats_ref": request.gwas_stats_ref,
                    "qtl_stats_ref": request.qtl_stats_ref},
        )})

    def _materialize(self, key: str, path: Path) -> Path:
        path.write_bytes(self.store.get(key))
        return path

    def _run(self, argv: list[str]) -> None:
        try:
            completed = subprocess.run(
                argv, check=False, capture_output=True, text=True,
                timeout=self.config.timeout_seconds,
            )
        except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
            raise RuntimeError(f"statistical executor unavailable: {exc}") from exc
        if completed.returncode:
            detail = completed.stderr.strip()[-1000:]
            raise RuntimeError(f"statistical executor failed ({completed.returncode}): {detail}")

    def _capture(self, argv: list[str]) -> str:
        try:
            completed = subprocess.run(
                argv, check=False, capture_output=True, text=True,
                timeout=min(self.config.timeout_seconds, 30),
            )
        except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
            raise RuntimeError(f"statistical executor unavailable: {exc}") from exc
        if completed.returncode:
            raise RuntimeError(completed.stderr.strip()[-1000:])
        return completed.stdout


class GwasWorkerBackend:
    """Persist typed executor results and expose the service backend contract."""

    name = "gwas_statistical_worker"

    def __init__(self, engine: StatisticalEngine, store: ObjectStore) -> None:
        self.engine, self.store = engine, store
        self.version = engine.revision

    def lookup_associations(self, request: GwasRequest) -> GwasResult:
        return GwasResult(
            confidence=Confidence(band=ConfidenceBand.UNKNOWN,
                                  basis="statistical worker does not query catalogs"),
            provenance=Provenance(tool=self.name, tool_version=self.version),
            coverage_note="use EBI or Open Targets adapter for catalog associations",
        )

    def compute_ld(self, request: LdRequest) -> LdResult:
        result = self.engine.compute_ld(request)
        return self._persist(result, "ld")

    def fine_map(self, request: FineMapRequest) -> FineMapResult:
        result = self.engine.fine_map(request)
        return self._persist(result, "fine-map")

    def coloc(self, request: ColocRequest) -> ColocBatchResult:
        result = self.engine.coloc(request)
        return self._persist(result, "coloc")

    def _persist(self, result, operation: str):  # noqa: ANN001, ANN202
        payload = result.model_dump_json(exclude={"storage_ref", "locus_plot_ref"}).encode()
        ref = self.store.put(payload, content_type="application/json")
        provenance = result.provenance.model_copy(update={"output_ref": ref.key,
                                                           "output_hash": ref.hash})
        return result.model_copy(update={"storage_ref": ref.key, "provenance": provenance})
