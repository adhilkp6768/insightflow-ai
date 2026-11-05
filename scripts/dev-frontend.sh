#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
export PATH="${HOME}/.local/node/bin:${PATH}"

if ! command -v npm >/dev/null 2>&1; then
  echo "npm was not found. Add ~/.local/node/bin to PATH." >&2
  exit 1
fi

cd "$ROOT/frontend"
if [[ ! -d node_modules ]]; then
  npm install
fi

exec npm run dev -- --host 127.0.0.1 --port 5173
