"""Network-free tests for the production ESMFold/Boltz-2 worker adapters."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest
from cellxp.domain.enums import SequenceAlphabet
from cellxp.domain.sequences import BiologicalSequence
from cellxp.services.structure.backends import (
    BOLTZ_MODEL_VERSION,
    ESMFOLD_REVISION,
    BoltzRunner,
    ProductionStructureBackend,
    StructureRuntimeConfig,
    _boltz_yaml,
)
from cellxp.services.structure.schemas import LigandSpec, StructureRequest
from cellxp.storage.object_store import FilesystemObjectStore


def _protein(seq: str = "MKTAYIAKQR") -> BiologicalSequence:
    return BiologicalSequence(seq=seq, alphabet=SequenceAlphabet.PROTEIN)


def test_runtime_config_rejects_non_positive_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("STRUCTURE_JOB_TIMEOUT_SECONDS", "0")
    with pytest.raises(ValueError, match="positive"):
        StructureRuntimeConfig.from_env()


def test_boltz_input_uses_local_single_sequence_mode_and_affinity() -> None:
    text = _boltz_yaml(
        StructureRequest(
            kind="complex",
            sequences=[_protein()],
            ligand=LigandSpec(format="smiles", value="CCO"),
        )
    )
    assert "msa: empty" in text
    assert 'smiles: "CCO"' in text
    assert "affinity:" in text
    assert "use_msa_server" not in text


def test_boltz_input_rejects_unstandardized_inchi() -> None:
    request = StructureRequest(
        kind="complex",
        sequences=[_protein()],
        ligand=LigandSpec(format="inchi", value="InChI=1S/CH4/h1H4"),
    )
    with pytest.raises(ValueError, match="standardized"):
        _boltz_yaml(request)


def test_boltz_runner_uses_argv_timeout_gpu_and_parses_outputs(tmp_path: Path) -> None:
    seen: dict[str, object] = {}

    def fake_run(argv: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        seen["argv"] = argv
        seen.update(kwargs)
        output = Path(argv[argv.index("--out_dir") + 1]) / "predictions" / "request"
        output.mkdir(parents=True)
        (output / "request_model_0.cif").write_bytes(b"data_cellxp\n")
        (output / "plddt_request_model_0.npz").write_bytes(b"fixture")
        (output / "affinity_request.json").write_text(
            json.dumps({"affinity_pred_value": -1.25}), encoding="utf-8"
        )
        return subprocess.CompletedProcess(argv, 0, "", "")

    runner = BoltzRunner(
        StructureRuntimeConfig(model_cache_dir=tmp_path, timeout_seconds=42),
        run=fake_run,
        npz_loader=lambda path: [0.8, 0.9],
    )
    coordinates, confidence, affinity = runner.predict(
        StructureRequest(
            kind="complex",
            sequences=[_protein()],
            ligand=LigandSpec(format="smiles", value="CCO"),
        )
    )

    argv = seen["argv"]
    assert isinstance(argv, list)
    assert argv[:2] == ["boltz", "predict"]
    assert argv[argv.index("--accelerator") + 1] == "gpu"
    assert seen["timeout"] == 42
    assert seen["check"] is False
    assert coordinates == b"data_cellxp\n"
    assert confidence == pytest.approx([0.8, 0.9])
    assert affinity == -1.25
    assert runner.version == BOLTZ_MODEL_VERSION


def test_boltz_runner_converts_timeout_to_bounded_error(tmp_path: Path) -> None:
    def timed_out(*args: object, **kwargs: object) -> subprocess.CompletedProcess[str]:
        raise subprocess.TimeoutExpired(cmd="boltz", timeout=3)

    runner = BoltzRunner(
        StructureRuntimeConfig(model_cache_dir=tmp_path, timeout_seconds=3), run=timed_out
    )
    with pytest.raises(RuntimeError, match="exceeded 3s"):
        runner.predict(StructureRequest(kind="complex", sequences=[_protein(), _protein()]))


class _FakeEsmFold:
    version = f"facebook/esmfold_v1@{ESMFOLD_REVISION}"

    def predict(self, sequence: str) -> tuple[bytes, list[float]]:
        assert sequence == "MKTAYIAKQR"
        return b"ATOM\n", [0.91] * len(sequence)


class _UnusedBoltz:
    version = BOLTZ_MODEL_VERSION

    def predict(self, request: StructureRequest) -> tuple[bytes, list[float], None]:
        raise AssertionError("Boltz should not be selected for a protein monomer")


def test_production_backend_persists_content_addressed_structure(tmp_path: Path) -> None:
    store = FilesystemObjectStore(tmp_path / "objects")
    backend = ProductionStructureBackend(
        object_store=store,
        config=StructureRuntimeConfig(device="cpu", model_cache_dir=tmp_path / "models"),
        esmfold=_FakeEsmFold(),  # type: ignore[arg-type]
        boltz=_UnusedBoltz(),  # type: ignore[arg-type]
    )
    result = backend.predict_structure(
        StructureRequest(kind="protein", sequences=[_protein()])
    )

    assert result.structure_ref is not None
    assert result.structure_ref.startswith("cas/")
    assert store.get(result.structure_ref) == b"ATOM\n"
    assert result.provenance.tool_version.endswith(ESMFOLD_REVISION)
    assert result.per_residue_confidence == [0.91] * 10
