#!/usr/bin/env bash
# Start the Next.js dev server (binds all interfaces for LAN access).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT/src/frontend"

# Load local overrides when present (NEXT_PUBLIC_API_BASE, CELLXP_API_PROXY_TARGET, …).
if [[ -f .env.local ]]; then
  set -a
  # shellcheck disable=SC1091
  source .env.local
  set +a
fi

export CELLXP_API_PROXY_TARGET="${CELLXP_API_PROXY_TARGET:-http://127.0.0.1:8001}"

exec npm run dev
