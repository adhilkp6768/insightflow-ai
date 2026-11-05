#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PYTHON="${HOME}/.local/python/bin/python3.11"

if [[ ! -x "$PYTHON" ]]; then
  echo "Python 3.11 was not found at $PYTHON" >&2
  exit 1
fi

cd "$ROOT/backend"
if [[ ! -d .venv ]]; then
  "$PYTHON" -m venv .venv
  .venv/bin/pip install -e ".[dev]"
fi

if [[ -f "$ROOT/.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "$ROOT/.env"
  set +a
fi

export JWT_SECRET="${JWT_SECRET:-local-development-secret-not-for-production-use}"
if [[ "${#JWT_SECRET}" -lt 32 ]]; then
  echo "JWT_SECRET must be at least 32 characters." >&2
  exit 1
fi

if [[ -z "${DATABASE_URL:-}" ]]; then
  echo "DATABASE_URL is unset. Using SQLite at backend/insightflow.dev.db."
  echo "Docker Compose with PostgreSQL and Redis is the supported stack."
  export DATABASE_URL="sqlite+pysqlite:///./insightflow.dev.db"
  export REDIS_URL="${REDIS_URL:-}"
fi

export ENVIRONMENT="${ENVIRONMENT:-development}"
export CORS_ORIGINS="${CORS_ORIGINS:-http://localhost:5173}"

echo "Cleaning, training, and the UCI import run in this process unless JOBS_INLINE=true."
.venv/bin/alembic upgrade head
exec .venv/bin/uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
