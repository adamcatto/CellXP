"""Production GPU adapters for ESMFold and Boltz-2.

The adapters live behind :class:`StructureBackend`, keep ESMFold warm in the worker
process, execute Boltz with an argv vector (never a shell), enforce hard timeouts, and
persist coordinate payloads through the configured immutable object store.
"""

from __future__ import annotations

import importlib
import json
import os
import shutil
import subprocess
import tempfile
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx

from cellxp.domain.enums import SequenceAlphabet
from cellxp.domain.evidence import Provenance
from cellxp.storage.object_store import ObjectStore

from .schemas import (
    ContactMapRequest,
    ContactMapResult,
    DnaShapeRequest,
    DnaShapeResult,
    StructureRequest,
    StructureResult,
)
from .transforms import select_structure_model

ESMFOLD_REPOSITORY = "facebook/esmfold_v1"
ESMFOLD_REVISION = "75a3841ee059df2bf4d56688166c8fb459ddd97a"
BOLTZ_PACKAGE_VERSION = "2.2.1"
BOLTZ_MODEL_VERSION = f"boltz2@{BOLTZ_PACKAGE_VERSION}"


@dataclass(frozen=True)
class StructureRuntimeConfig:
    """Worker-local inference settings; all paths and limits are deployment controlled."""

    device: str = "cuda"
    timeout_seconds: int = 1800
    model_cache_dir: Path = Path("/models")
    boltz_executable: str = "boltz"
    esmfold_revision: str = ESMFOLD_REVISION

    @classmethod
    def from_env(cls) -> StructureRuntimeConfig:
        timeout = int(os.getenv("STRUCTURE_JOB_TIMEOUT_SECONDS", "1800"))
        if timeout < 1:
            raise ValueError("STRUCTURE_JOB_TIMEOUT_SECONDS must be positive")
        device = os.getenv("STRUCTURE_DEVICE", "cuda")
        if device not in {"cuda", "cpu"}:
            raise ValueError("STRUCTURE_DEVICE must be 'cuda' or 'cpu'")
        return cls(
            device=device,
            timeout_seconds=timeout,
            model_cache_dir=Path(os.getenv("MODEL_CACHE_DIR", "/models")),
            boltz_executable=os.getenv("BOLTZ_EXECUTABLE", "boltz"),
            esmfold_revision=os.getenv("ESMFOLD_REVISION", ESMFOLD_REVISION),
        )


class EsmFoldRunner:
    """Lazy, warm-loaded Hugging Face ESMFold runner."""

    def __init__(
        self,
        config: StructureRuntimeConfig,
        *,
        loader: Callable[[StructureRuntimeConfig], tuple[Any, Any, Any]] | None = None,
    ) -> None:
        self.config = config
        self._loader = loader or _load_esmfold
        self._loaded: tuple[Any, Any, Any] | None = None

    @property
    def version(self) -> str:
        return f"{ESMFOLD_REPOSITORY}@{self.config.esmfold_revision}"

    def predict(self, sequence: str) -> tuple[bytes, list[float]]:
        if self._loaded is None:
            self._loaded = self._loader(self.config)
        tokenizer, model, torch = self._loaded
        encoded = tokenizer([sequence], return_tensors="pt", add_special_tokens=False)
        encoded = {key: value.to(self.config.device) for key, value in encoded.items()}
        with torch.no_grad():
            outputs = model(**encoded)
        pdb = model.output_to_pdb(outputs)[0].encode("utf-8")
        scores = outputs.plddt.detach().float().cpu()
        # Transformers exposes atom37 pLDDT; CA (index 1) is the residue score.
        if len(scores.shape) == 3:
            scores = scores[0, :, 1]
        else:
            scores = scores[0]
        confidence = [float(value) / 100.0 for value in scores.tolist()]
        return pdb, confidence


def _load_esmfold(config: StructureRuntimeConfig) -> tuple[Any, Any, Any]:
    try:
        torch = importlib.import_module("torch")
        transformers = importlib.import_module("transformers")
    except ImportError as exc:  # pragma: no cover - exercised only by live workers
        raise RuntimeError("ESMFold runtime dependencies are not installed") from exc

    if config.device == "cuda" and not torch.cuda.is_available():
        raise RuntimeError("STRUCTURE_DEVICE=cuda but CUDA is unavailable")
    kwargs = {
        "revision": config.esmfold_revision,
        "cache_dir": str(config.model_cache_dir / "huggingface"),
        "local_files_only": True,
    }
    tokenizer = transformers.AutoTokenizer.from_pretrained(ESMFOLD_REPOSITORY, **kwargs)
    model = transformers.EsmForProteinFolding.from_pretrained(ESMFOLD_REPOSITORY, **kwargs)
    model = model.eval().to(config.device)
    if config.device == "cuda":
        model.esm = model.esm.half()
        torch.backends.cuda.matmul.allow_tf32 = True
    return tokenizer, model, torch


class BoltzRunner:
    """Isolated Boltz-2 CLI runner with deterministic local single-sequence inputs."""

    def __init__(
        self,
        config: StructureRuntimeConfig,
        *,
        run: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
        npz_loader: Callable[[Path], list[float]] | None = None,
    ) -> None:
        self.config = config
        self._run = run
        self._npz_loader = npz_loader or _load_npz_values

    @property
    def version(self) -> str:
        return BOLTZ_MODEL_VERSION

    def predict(self, request: StructureRequest) -> tuple[bytes, list[float], float | None]:
        with tempfile.TemporaryDirectory(prefix="cellxp-boltz-") as tmp:
            root = Path(tmp)
            input_path = root / "request.yaml"
            output_dir = root / "output"
            input_path.write_text(_boltz_yaml(request), encoding="utf-8")
            argv = [
                self.config.boltz_executable,
                "predict",
                str(input_path),
                "--out_dir",
                str(output_dir),
                "--cache",
                str(self.config.model_cache_dir / "boltz"),
                "--accelerator",
                "gpu" if self.config.device == "cuda" else "cpu",
                "--devices",
                "1",
                "--output_format",
                "mmcif",
                "--override",
            ]
            try:
                completed = self._run(
                    argv,
                    check=False,
                    capture_output=True,
                    text=True,
                    timeout=self.config.timeout_seconds,
                )
            except subprocess.TimeoutExpired as exc:
                raise RuntimeError(
                    f"Boltz-2 exceeded {self.config.timeout_seconds}s timeout"
                ) from exc
            if completed.returncode != 0:
                detail = (completed.stderr or completed.stdout)[-2000:].strip()
                raise RuntimeError(f"Boltz-2 failed with exit {completed.returncode}: {detail}")

            predictions = output_dir / "predictions" / "request"
            cif = _one_file(predictions, "request_model_0.cif")
            confidence = self._npz_loader(
                _one_file(predictions, "plddt_request_model_0.npz")
            )
            affinity_path = predictions / "affinity_request.json"
            affinity = None
            if affinity_path.exists():
                payload = json.loads(affinity_path.read_text(encoding="utf-8"))
                affinity = float(payload["affinity_pred_value"])
            return cif.read_bytes(), confidence, affinity


def _one_file(directory: Path, name: str) -> Path:
    path = directory / name
    if not path.is_file():
        raise RuntimeError(f"Boltz-2 did not produce expected output {name!r}")
    return path


def _load_npz_values(path: Path) -> list[float]:
    try:
        np = importlib.import_module("numpy")
    except ImportError as exc:  # pragma: no cover - installed with Boltz
        raise RuntimeError("numpy is required to read Boltz-2 confidence output") from exc
    with np.load(path, allow_pickle=False) as data:
        key = "plddt" if "plddt" in data.files else data.files[0]
        return [float(value) for value in data[key].reshape(-1).tolist()]


def _boltz_yaml(request: StructureRequest) -> str:
    lines = ["version: 1", "sequences:"]
    chain_ids = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    for index, sequence in enumerate(request.sequences):
        entity = {
            SequenceAlphabet.PROTEIN: "protein",
            SequenceAlphabet.DNA: "dna",
            SequenceAlphabet.RNA: "rna",
        }[sequence.alphabet]
        lines.extend(
            [
                f"  - {entity}:",
                f"      id: {chain_ids[index]}",
                f"      sequence: {json.dumps(sequence.seq)}",
            ]
        )
        if entity == "protein":
            lines.append("      msa: empty")
    if request.ligand is not None:
        ligand_id = chain_ids[len(request.sequences)]
        lines.extend(["  - ligand:", f"      id: {ligand_id}"])
        key = "ccd" if request.ligand.format == "ccd" else "smiles"
        if request.ligand.format == "inchi":
            raise ValueError("Boltz-2 accepts SMILES or CCD ligands; InChI must be standardized first")
        lines.append(f"      {key}: {json.dumps(request.ligand.value)}")
        lines.extend(["properties:", "  - affinity:", f"      binder: {ligand_id}"])
    return "\n".join(lines) + "\n"


class ProductionStructureBackend:
    """StructureBackend implementation intended to be instantiated once per GPU worker."""

    def __init__(
        self,
        *,
        object_store: ObjectStore,
        config: StructureRuntimeConfig | None = None,
        esmfold: EsmFoldRunner | None = None,
        boltz: BoltzRunner | None = None,
    ) -> None:
        self.config = config or StructureRuntimeConfig.from_env()
        self.object_store = object_store
        self.esmfold = esmfold or EsmFoldRunner(self.config)
        self.boltz = boltz or BoltzRunner(self.config)

    def predict_structure(self, request: StructureRequest) -> StructureResult:
        model = select_structure_model(
            request.kind,
            n_chains=len(request.sequences),
            has_ligand=request.ligand is not None,
        )
        if model == "esmfold":
            coordinates, confidence = self.esmfold.predict(request.sequences[0].seq)
            content_type, version, affinity = "chemical/x-pdb", self.esmfold.version, None
        else:
            coordinates, confidence, affinity = self.boltz.predict(request)
            content_type, version = "chemical/x-mmcif", self.boltz.version
        ref = self.object_store.put(coordinates, content_type=content_type)
        return StructureResult(
            structure_ref=ref.key,
            per_residue_confidence=confidence,
            affinity=affinity,
            model=model,
            provenance=Provenance(tool=model, tool_version=version, output_ref=ref.key),
        )

    def predict_contacts(self, request: ContactMapRequest) -> ContactMapResult:
        raise NotImplementedError("Orca worker is not configured by this backend")

    def predict_dna_shape(self, request: DnaShapeRequest) -> DnaShapeResult:
        raise NotImplementedError("DNAshapeR worker is not configured by this backend")


def validate_worker_runtime(config: StructureRuntimeConfig) -> None:
    """Fail fast on invalid worker images before accepting GPU jobs."""

    if not shutil.which(config.boltz_executable):
        raise RuntimeError(f"Boltz executable not found: {config.boltz_executable!r}")
    if config.esmfold_revision != ESMFOLD_REVISION:
        raise RuntimeError("ESMFOLD_REVISION must match the release-pinned revision")


class RemoteStructureBackend:
    """Client for the isolated structure worker HTTP boundary."""

    def __init__(self, base_url: str, *, timeout_seconds: float = 1800) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds

    def predict_structure(self, request: StructureRequest) -> StructureResult:
        try:
            response = httpx.post(
                f"{self.base_url}/v1/predict",
                json=request.model_dump(mode="json"),
                timeout=self.timeout_seconds,
            )
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise RuntimeError(f"structure worker request failed: {exc}") from exc
        return StructureResult.model_validate(response.json())

    def predict_contacts(self, request: ContactMapRequest) -> ContactMapResult:
        raise NotImplementedError("remote Orca worker is not configured")

    def predict_dna_shape(self, request: DnaShapeRequest) -> DnaShapeResult:
        raise NotImplementedError("remote DNAshapeR worker is not configured")
