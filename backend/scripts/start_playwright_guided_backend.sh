#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

PORT="${PORT:-8003}"
DATABASE_URL="${DATABASE_URL:-postgresql+asyncpg://postgres:postgres@localhost:5432/esgdashboard_demo_20260323}"
DEMO_BASE_URL="${DEMO_BASE_URL:-http://localhost:3003}"
DEMO_API_URL="${DEMO_API_URL:-http://localhost:${PORT}/api}"
CORS_ORIGINS="${CORS_ORIGINS:-[\"${DEMO_BASE_URL}\"]}"
DB_REQUIRE_CURRENT_REVISION="${DB_REQUIRE_CURRENT_REVISION:-true}"
RATE_LIMIT_PER_MINUTE="${RATE_LIMIT_PER_MINUTE:-500}"

export PORT
export DATABASE_URL
export DEMO_BASE_URL
export DEMO_API_URL
export CORS_ORIGINS
export DB_REQUIRE_CURRENT_REVISION
export RATE_LIMIT_PER_MINUTE

cd "${BACKEND_DIR}"

# Rebuild the demo dataset before each Playwright run so guided flows test current schema.
./.venv/bin/python scripts/seed_demo_env.py

exec ./.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port "${PORT}"
