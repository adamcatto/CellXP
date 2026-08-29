from __future__ import annotations

import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).parents[2]


def run_script(*args: str, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(ROOT / args[0]), *args[1:]],
        cwd="/tmp",
        env={**os.environ, **(env or {})},
        check=False,
        capture_output=True,
        text=True,
    )


def test_setup_help_documents_bootstrap_prerequisites() -> None:
    result = run_script("scripts/setup.sh", "--help")

    assert result.returncode == 0
    assert "Prerequisites: Conda, NVM, Corepack, and Docker" in result.stdout


def test_setup_dry_run_can_skip_external_toolchains() -> None:
    result = run_script(
        "scripts/setup.sh",
        "--dry-run",
        "--skip-backend",
        "--skip-frontend",
        "--skip-infra",
        "--skip-models",
    )

    assert result.returncode == 0
    assert "CellXP setup complete" in result.stdout


def test_model_dry_run_discovers_and_deduplicates_role_models(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(
        "LLM_PROVIDER=ollama\n"
        "LLM_MODEL=gemma4:4b\n"
        "LLM_MODEL_PLANNER=gemma4:12b\n"
        "LLM_MODEL_WRITER=gemma4:4b\n"
    )

    result = run_script(
        "scripts/download_models.sh",
        "--dry-run",
        "--runtime",
        "compose",
        "--env-file",
        str(env_file),
        env={"LLM_PROVIDER": "", "LLM_MODEL": ""},
    )

    assert result.returncode == 0
    assert result.stdout.count("Pulling Ollama model: gemma4:4b") == 1
    assert result.stdout.count("Pulling Ollama model: gemma4:12b") == 1


def test_remote_provider_skips_download(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text("LLM_PROVIDER=openai\nLLM_MODEL=gpt-example\n")

    result = run_script(
        "scripts/download_models.sh",
        "--env-file",
        str(env_file),
        env={"LLM_PROVIDER": "", "LLM_MODEL": ""},
    )

    assert result.returncode == 0
    assert "uses remote models; nothing to download" in result.stdout


def test_model_name_rejects_shell_metacharacters() -> None:
    result = run_script(
        "scripts/download_models.sh",
        "--dry-run",
        "--runtime",
        "compose",
        "--model",
        "bad;model",
    )

    assert result.returncode != 0
    assert "invalid Ollama model name" in result.stderr


def test_structure_model_dry_run_uses_immutable_revisions(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text("LLM_PROVIDER=openai\n")
    result = run_script(
        "scripts/download_models.sh",
        "--dry-run",
        "--env-file",
        str(env_file),
        "--cache-dir",
        str(tmp_path / "models"),
        "--structure",
        "all",
        env={"LLM_PROVIDER": ""},
    )

    assert result.returncode == 0
    assert "75a3841ee059df2bf4d56688166c8fb459ddd97a" in result.stdout
    assert "boltz==2.2.1" in result.stdout
    assert "ollama pull" not in result.stdout


def test_structure_model_rejects_unknown_name() -> None:
    result = run_script(
        "scripts/download_models.sh", "--dry-run", "--structure", "bad;model"
    )
    assert result.returncode != 0
    assert "structure model must be" in result.stderr
