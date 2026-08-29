"""Opt-in T7 smoke tests for pinned ESMFold and Boltz-2 GPU inference."""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from cellxp.domain.enums import SequenceAlphabet
from cellxp.domain.sequences import BiologicalSequence
from cellxp.services.structure.backends import ProductionStructureBackend, StructureRuntimeConfig
from cellxp.services.structure.schemas import StructureRequest
from cellxp.storage.object_store import FilesystemObjectStore

pytestmark = [pytest.mark.live, pytest.mark.gpu, pytest.mark.slow]


def _backend(tmp_path: Path) -> ProductionStructureBackend:
    if os.getenv("CELLXP_LIVE_STRUCTURE") != "1":
        pytest.skip("set CELLXP_LIVE_STRUCTURE=1 to run live structure inference")
    return ProductionStructureBackend(
        object_store=FilesystemObjectStore(tmp_path / "objects"),
        config=StructureRuntimeConfig.from_env(),
    )


def _protein(sequence: str) -> BiologicalSequence:
    return BiologicalSequence(seq=sequence, alphabet=SequenceAlphabet.PROTEIN)


def test_live_esmfold_smoke(tmp_path: Path) -> None:
    result = _backend(tmp_path).predict_structure(
        StructureRequest(kind="protein", sequences=[_protein("MKTAYIAKQRQISFVKSHFSRQ")])
    )
    assert result.model == "esmfold"
    assert result.structure_ref is not None
    assert len(result.per_residue_confidence or []) == 22


def test_live_boltz2_smoke(tmp_path: Path) -> None:
    result = _backend(tmp_path).predict_structure(
        StructureRequest(
            kind="complex",
            sequences=[_protein("MKTAYIAKQR"), _protein("GILGFVFTL")],
        )
    )
    assert result.model == "boltz2"
    assert result.structure_ref is not None
    assert result.per_residue_confidence
