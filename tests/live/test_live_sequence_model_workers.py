"""Opt-in deployed-worker acceptance; results are evidence only when actually executed."""

from __future__ import annotations

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
