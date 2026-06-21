#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DRY_RUN=0
SKIP_BACKEND=0
SKIP_FRONTEND=0
SKIP_INFRA=0
SKIP_MODELS=0

usage() {
  cat <<'EOF'
Usage: scripts/setup.sh [options]

Bootstrap a CellXP development checkout. The script is safe to rerun: it
synchronizes the Conda environment, frontend lockfile, Compose services, and
configured Ollama models.

Prerequisites: Conda, NVM, Corepack, and Docker with Compose v2.

Options:
  --skip-backend    Do not create/update the Conda environment
  --skip-frontend   Do not install Node/pnpm dependencies
  --skip-infra      Do not start Docker Compose services
  --skip-models     Do not download configured Ollama models
  --dry-run         Print operations without changing the host
  -h, --help        Show this help
EOF
}

die() {
  printf 'error: %s\n' "$*" >&2
  exit 1
}

run() {
  printf '+ '
  printf '%q ' "$@"
  printf '\n'
  ((DRY_RUN)) || "$@"
}

while (($#)); do
  case "$1" in
    --skip-backend) SKIP_BACKEND=1 ;;
    --skip-frontend) SKIP_FRONTEND=1 ;;
    --skip-infra) SKIP_INFRA=1 ;;
    --skip-models) SKIP_MODELS=1 ;;
    --dry-run) DRY_RUN=1 ;;
    -h|--help) usage; exit 0 ;;
    *) die "unknown option: $1" ;;
  esac
  shift
done

cd "${ROOT_DIR}"

if [[ ! -f .env ]]; then
  run cp .env.example .env
else
  printf 'Keeping existing .env.\n'
fi

if ((!SKIP_BACKEND)); then
  command -v conda >/dev/null 2>&1 || die "conda is required (or pass --skip-backend)"
  if conda run -n cellxp true >/dev/null 2>&1; then
    run conda env update -n cellxp -f environment.yml --prune
  else
    run conda env create -f environment.yml
  fi
fi

if ((!SKIP_FRONTEND)); then
  export NVM_DIR="${NVM_DIR:-${HOME}/.nvm}"
  if [[ -s "${NVM_DIR}/nvm.sh" ]]; then
    # shellcheck source=/dev/null
    source "${NVM_DIR}/nvm.sh"
  fi
  command -v nvm >/dev/null 2>&1 || die "nvm is required (or pass --skip-frontend)"
  run nvm install
  run nvm use
  command -v corepack >/dev/null 2>&1 || die "corepack is required after selecting Node"
  run corepack enable
  run corepack prepare pnpm@10.17.0 --activate
  run pnpm --dir src/frontend install --frozen-lockfile
fi

if ((!SKIP_INFRA)); then
  command -v docker >/dev/null 2>&1 || die "docker is required (or pass --skip-infra)"
  run docker compose version
  run docker compose -f docker-compose.yml up -d
fi

if ((!SKIP_MODELS)); then
  model_args=()
  ((DRY_RUN)) && model_args+=(--dry-run)
  if ((SKIP_INFRA)); then
    model_args+=(--runtime auto)
  else
    model_args+=(--runtime compose)
  fi
  run "${ROOT_DIR}/scripts/download_models.sh" "${model_args[@]}"
fi

printf '\nCellXP setup complete. Activate the backend with: conda activate cellxp\n'
