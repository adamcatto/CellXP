"""Checksum verification for explicit model acquisition."""

from __future__ import annotations

import hashlib
import json

import pytest

from scripts.acquire_sequence_model import acquire


def test_acquisition_accepts_only_manifest_checksum(tmp_path) -> None:
    source = tmp_path / "source.bin"
    source.write_bytes(b"pinned model fixture")
    checksum = hashlib.sha256(source.read_bytes()).hexdigest()
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps({"weights": [{
        "filename": "weights.bin", "url": source.as_uri(), "sha256": checksum
    }]}))

    acquired = acquire(manifest, tmp_path / "models")
    assert acquired[0].read_bytes() == source.read_bytes()


def test_acquisition_removes_checksum_mismatch(tmp_path) -> None:
    source = tmp_path / "source.bin"
    source.write_bytes(b"wrong bytes")
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps({"weights": [{
        "filename": "weights.bin", "url": source.as_uri(), "sha256": "0" * 64
    }]}))

    with pytest.raises(ValueError, match="checksum mismatch"):
        acquire(manifest, tmp_path / "models")
    assert not (tmp_path / "models" / "weights.bin").exists()
