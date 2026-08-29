"""Opt-in verification that official pinned source archives still match recorded bytes."""

from __future__ import annotations

import hashlib
import os
import urllib.request

import pytest
from cellxp.services.crispr.worker_contract import packaged_worker_manifest

pytestmark = [pytest.mark.live, pytest.mark.slow]


def test_official_crispr_source_archive_checksums() -> None:
    if os.getenv("CELLXP_VERIFY_CRISPR_UPSTREAM") != "1":
        pytest.skip("set CELLXP_VERIFY_CRISPR_UPSTREAM=1 for the large upstream archive check")
    for source in packaged_worker_manifest().sources:
        digest = hashlib.sha256()
        with urllib.request.urlopen(source.archive_url, timeout=300) as response:
            while chunk := response.read(1024 * 1024):
                digest.update(chunk)
        assert digest.hexdigest() == source.archive_sha256, source.name
