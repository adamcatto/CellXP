#!/usr/bin/env bash
# Start the CellXP API for local / LAN frontend development.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

PORT="${CELLXP_API_PORT:-8001}"
HOST="${CELLXP_API_HOST:-0.0.0.0}"

export RUNTIME_BACKEND="${RUNTIME_BACKEND:-local}"
export DATABASE_URL="${DATABASE_URL:-sqlite:///./.cellxp/runtime.db}"

# Optional: allow direct browser → API calls without the Next.js proxy.
# Example: CELLXP_CORS_ORIGINS=http://10.81.105.76:3000
export CELLXP_CORS_ORIGINS="${CELLXP_CORS_ORIGINS:-}"

VENV_PY="${ROOT}/.venv/bin/python"
if [[ ! -x "$VENV_PY" ]]; then
  echo "error: ${VENV_PY} not found. Run ./scripts/setup.sh (or create .venv) first." >&2
  exit 1
fi

# Editable install adds src/backend via .pth; PYTHONPATH covers bare checkouts too.
export PYTHONPATH="${ROOT}/src/backend${PYTHONPATH:+:${PYTHONPATH}}"

if ! "$VENV_PY" -c "import cellxp.api.main" >/dev/null 2>&1; then
  echo "error: cannot import cellxp.api.main (PYTHONPATH=${PYTHONPATH})." >&2
  echo "hint: reinstall the package in the venv, e.g. uv pip install -e . from ${ROOT}" >&2
  exit 1
fi

_port_in_use_pids() {
  local port="$1"
  local pids=""
  if command -v lsof >/dev/null 2>&1; then
    pids="$(lsof -tiTCP:"$port" -sTCP:LISTEN 2>/dev/null | sort -u | tr '\n' ' ' | sed 's/ $//')"
  fi
  if [[ -z "$pids" ]] && command -v ss >/dev/null 2>&1; then
    pids="$(ss -tlnp "sport = :$port" 2>/dev/null | grep -oE 'pid=[0-9]+' | cut -d= -f2 | sort -u | tr '\n' ' ' | sed 's/ $//')"
  fi
  echo "$pids"
}

if listeners="$(_port_in_use_pids "$PORT")" && [[ -n "$listeners" ]]; then
  echo "error: port ${PORT} is already in use (PID(s): ${listeners})." >&2
  for pid in $listeners; do
    if cmd="$(ps -p "$pid" -o args= 2>/dev/null)"; then
      echo "  pid ${pid}: ${cmd}" >&2
    fi
  done
  echo "hint: stop the listener (foreground: Ctrl+C; background: kill -TERM ${listeners})" >&2
  echo "      or start on another port: CELLXP_API_PORT=8002 $0" >&2
  exit 1
fi

exec "$VENV_PY" -m uvicorn cellxp.api.main:app --reload --host "$HOST" --port "$PORT"
