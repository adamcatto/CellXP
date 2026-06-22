"""Opt-in deployed CRISPR worker acceptance; skipped without explicit authorization."""

from __future__ import annotations

import os

import httpx
import pytest

pytestmark = [pytest.mark.live, pytest.mark.slow]


def test_live_worker_attestation_and_human_microbe_routing() -> None:
    base_url = os.getenv("CELLXP_LIVE_CRISPR_URL")
    if not base_url:
        pytest.skip("set CELLXP_LIVE_CRISPR_URL to run deployed CRISPR acceptance")
    with httpx.Client(base_url=base_url, timeout=300) as client:
        health = client.get("/health")
        health.raise_for_status()
        attestation = health.json()
        assert attestation["status"] == "ok"
        assert attestation["mode"] == "production"
        assert {"cas-offinder", "azimuth-rule-set-2", "crispor-cfd"} <= set(
            attestation["source_revisions"]
        )
        for organism, assembly in (
            ("Homo sapiens", os.getenv("CELLXP_CRISPR_HUMAN_ASSEMBLY", "GRCh38")),
            ("Escherichia coli", os.getenv("CELLXP_CRISPR_MICROBIAL_ASSEMBLY", "GCF_000005845.2")),
        ):
            response = client.post("/v1/on-target-scores", json={
                "guides": ["GAGTCCGAGCAGAAGAAGAA"],
                "organism": organism,
                "assembly": assembly,
                "model": "auto",
            })
            response.raise_for_status()
            assert 0 <= next(iter(response.json()["scores"].values())) <= 1
