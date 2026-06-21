#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="${CELLXP_ENV_FILE:-${ROOT_DIR}/.env}"
RUNTIME="auto"
DRY_RUN=0
declare -a REQUESTED_MODELS=()

usage() {
  cat <<'EOF'
Usage: scripts/download_models.sh [options]

Download the local reasoning models configured for CellXP.

Options:
  --model NAME       Pull NAME instead of models configured in .env (repeatable)
  --runtime MODE     auto (default), compose, or host
  --env-file PATH    Read model configuration from PATH
  --dry-run          Print the pulls without running them
  -h, --help         Show this help

The default set is LLM_MODEL plus any LLM_MODEL_<ROLE> values. If no env file
exists, LLM_MODEL defaults to gemma4:4b. Remote LLM providers require no pull.
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
if [[ "${provider}" != "ollama" && ${#REQUESTED_MODELS[@]} -eq 0 ]]; then
  printf 'LLM provider %s uses remote models; nothing to download.\n' "${provider}"
  exit 0
fi

if ((${#REQUESTED_MODELS[@]} == 0)); then
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

if [[ "${RUNTIME}" == "auto" ]]; then
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
