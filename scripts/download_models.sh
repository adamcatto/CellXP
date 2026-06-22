#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="${CELLXP_ENV_FILE:-${ROOT_DIR}/.env}"
RUNTIME="auto"
DRY_RUN=0
declare -a REQUESTED_MODELS=()
declare -a STRUCTURE_MODELS=()
MODEL_CACHE_DIR="${MODEL_CACHE_DIR:-${ROOT_DIR}/.cache/models}"
ESMFOLD_REPOSITORY="facebook/esmfold_v1"
ESMFOLD_REVISION="75a3841ee059df2bf4d56688166c8fb459ddd97a"
BOLTZ_VERSION="2.2.1"

usage() {
  cat <<'EOF'
Usage: scripts/download_models.sh [options]

Download the local reasoning models configured for CellXP.

Options:
  --model NAME       Pull NAME instead of models configured in .env (repeatable)
  --structure NAME   Download esmfold, boltz2, or all structure weights (repeatable)
  --cache-dir PATH   Domain-model cache root (default: .cache/models)
  --runtime MODE     auto (default), compose, or host
  --env-file PATH    Read model configuration from PATH
  --dry-run          Print the pulls without running them
  -h, --help         Show this help

The default set is LLM_MODEL plus any LLM_MODEL_<ROLE> values. Structure downloads
are always opt-in and use immutable model/package revisions. No models are downloaded
in --dry-run mode. Remote LLM providers require no reasoning-model pull.
EOF
}

die() {
  printf 'error: %s\n' "$*" >&2
  exit 1
}

read_env_value() {
  local key="$1"
  [[ -f "${ENV_FILE}" ]] || return 0
  sed -n -E "s/^[[:space:]]*${key}[[:space:]]*=[[:space:]]*([^#[:space:]]+).*$/\\1/p" \
    "${ENV_FILE}" | tail -n 1
}

while (($#)); do
  case "$1" in
    --model)
      (($# >= 2)) || die "--model requires a value"
      REQUESTED_MODELS+=("$2")
      shift 2
      ;;
    --runtime)
      (($# >= 2)) || die "--runtime requires a value"
      RUNTIME="$2"
      shift 2
      ;;
    --structure)
      (($# >= 2)) || die "--structure requires a value"
      STRUCTURE_MODELS+=("$2")
      shift 2
      ;;
    --cache-dir)
      (($# >= 2)) || die "--cache-dir requires a value"
      MODEL_CACHE_DIR="$2"
      shift 2
      ;;
    --env-file)
      (($# >= 2)) || die "--env-file requires a value"
      ENV_FILE="$2"
      shift 2
      ;;
    --dry-run)
      DRY_RUN=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *) die "unknown option: $1" ;;
  esac
done

[[ "${RUNTIME}" =~ ^(auto|compose|host)$ ]] || die "runtime must be auto, compose, or host"

provider="${LLM_PROVIDER:-$(read_env_value LLM_PROVIDER)}"
provider="${provider:-ollama}"
if [[ "${provider}" != "ollama" && ${#REQUESTED_MODELS[@]} -eq 0 && ${#STRUCTURE_MODELS[@]} -eq 0 ]]; then
  printf 'LLM provider %s uses remote models; nothing to download.\n' "${provider}"
  exit 0
fi

if ((${#REQUESTED_MODELS[@]} == 0)) && [[ "${provider}" == "ollama" ]]; then
  default_model="${LLM_MODEL:-$(read_env_value LLM_MODEL)}"
  REQUESTED_MODELS+=("${default_model:-gemma4:4b}")
  if [[ -f "${ENV_FILE}" ]]; then
    while IFS= read -r model; do
      [[ -n "${model}" ]] && REQUESTED_MODELS+=("${model}")
    done < <(sed -n -E \
      's/^[[:space:]]*LLM_MODEL_[A-Z0-9_]+[[:space:]]*=[[:space:]]*([^#[:space:]]+).*$/\1/p' \
      "${ENV_FILE}")
  fi
fi

if [[ "${provider}" == "ollama" && "${RUNTIME}" == "auto" ]]; then
  if command -v docker >/dev/null 2>&1 && \
    docker compose -f "${ROOT_DIR}/docker-compose.yml" ps --status running --services 2>/dev/null \
      | grep -qx ollama; then
    RUNTIME="compose"
  elif command -v ollama >/dev/null 2>&1; then
    RUNTIME="host"
  elif ((DRY_RUN)); then
    RUNTIME="compose"
  else
    die "no running Compose Ollama service or host ollama command found"
  fi
fi

declare -A SEEN=()
for model in "${REQUESTED_MODELS[@]}"; do
  [[ "${model}" =~ ^[A-Za-z0-9._:/-]+$ ]] || die "invalid Ollama model name: ${model}"
  [[ -z "${SEEN[${model}]:-}" ]] || continue
  SEEN["${model}"]=1

  if [[ "${RUNTIME}" == "compose" ]]; then
    command=(docker compose -f "${ROOT_DIR}/docker-compose.yml" exec -T ollama ollama pull "${model}")
  else
    command=(ollama pull "${model}")
  fi

  printf 'Pulling Ollama model: %s\n' "${model}"
  if ((DRY_RUN)); then
    printf '  '
    printf '%q ' "${command[@]}"
    printf '\n'
  else
    "${command[@]}"
  fi
done

declare -A SEEN_STRUCTURE=()
for requested in "${STRUCTURE_MODELS[@]}"; do
  [[ "${requested}" =~ ^(esmfold|boltz2|all)$ ]] || die "structure model must be esmfold, boltz2, or all"
  if [[ "${requested}" == "all" ]]; then
    models=(esmfold boltz2)
  else
    models=("${requested}")
  fi
  for model in "${models[@]}"; do
    [[ -z "${SEEN_STRUCTURE[${model}]:-}" ]] || continue
    SEEN_STRUCTURE["${model}"]=1
    if [[ "${model}" == "esmfold" ]]; then
      command=(huggingface-cli download "${ESMFOLD_REPOSITORY}" --revision "${ESMFOLD_REVISION}" --cache-dir "${MODEL_CACHE_DIR}/huggingface")
      printf 'Downloading ESMFold weights: %s@%s\n' "${ESMFOLD_REPOSITORY}" "${ESMFOLD_REVISION}"
    else
      command=(python -c 'from pathlib import Path; from boltz.main import download_boltz2; import sys; download_boltz2(Path(sys.argv[1]))' "${MODEL_CACHE_DIR}/boltz")
      printf 'Downloading Boltz-2 weights with boltz==%s\n' "${BOLTZ_VERSION}"
    fi
    if ((DRY_RUN)); then
      printf '  '
      printf '%q ' "${command[@]}"
      printf '\n'
    else
      if [[ "${model}" == "esmfold" ]]; then
        command -v huggingface-cli >/dev/null 2>&1 || die "huggingface-cli is required for ESMFold download"
      else
        installed_boltz="$(python -c 'from importlib.metadata import version; print(version("boltz"))' 2>/dev/null || true)"
        [[ "${installed_boltz}" == "${BOLTZ_VERSION}" ]] || die "boltz==${BOLTZ_VERSION} is required (found ${installed_boltz:-none})"
      fi
      mkdir -p "${MODEL_CACHE_DIR}"
      "${command[@]}"
    fi
  done
done
