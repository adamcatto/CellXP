"""Opt-in deployed-worker acceptance; results are evidence only when actually executed."""

from __future__ import annotations

import math
import os

import httpx
import pytest

pytestmark = [pytest.mark.live, pytest.mark.gpu, pytest.mark.slow]


@pytest.mark.parametrize(
    ("url_env", "expected_model"),
    [("CELLXP_LIVE_ALPHAGENOME_URL", "alphagenome"), ("CELLXP_LIVE_EVO2_URL", "evo2")],
)
def test_deployed_worker_health_and_version(url_env: str, expected_model: str) -> None:
    base_url = os.getenv(url_env)
    if not base_url:
        pytest.skip(f"set {url_env} to run deployed worker acceptance")
    with httpx.Client(base_url=base_url, timeout=30) as client:
        health = client.get("/health")
        health.raise_for_status()
        version = client.get("/version")
        version.raise_for_status()
    assert health.json()["status"] == "ok"
    assert health.json()["mode"] == "production"
    assert version.json()["model"] == expected_model
    assert version.json()["model_revision"] == health.json()["model_revision"]


def test_live_alphagenome_variant_inference() -> None:
    base_url = os.getenv("CELLXP_LIVE_ALPHAGENOME_URL")
    if not base_url:
        pytest.skip("set CELLXP_LIVE_ALPHAGENOME_URL after configuring ALPHAGENOME_API_KEY")
    with httpx.Client(base_url=base_url, timeout=300) as client:
        response = client.post("/v1/score-variants", json={
            "variants": [{
                "chrom": "chr22", "pos": 36201697, "ref": "A", "alt": "C",
                "assembly": "GRCh38",
            }],
            "organism": "Homo sapiens", "assembly": "GRCh38",
        })
        response.raise_for_status()
    effects = response.json()["per_variant"]
    assert len(effects) == 1
    assert effects[0]["deltas"]
    assert all(math.isfinite(item["value"]) for item in effects[0]["deltas"])


def test_live_evo2_sequence_likelihood_inference() -> None:
    base_url = os.getenv("CELLXP_LIVE_EVO2_URL")
    if not base_url:
        pytest.skip("set CELLXP_LIVE_EVO2_URL after mounting the pinned checkpoint")
    with httpx.Client(base_url=base_url, timeout=300) as client:
        response = client.post("/v1/score-sequences", json={
            "sequences": ["ACGT" * 32], "organism": "Escherichia coli",
            "assembly": "GCF_000005845.2", "scoring_type": "likelihood",
        })
        response.raise_for_status()
    assert len(response.json()["scores"]) == 1
    assert math.isfinite(response.json()["scores"][0])
