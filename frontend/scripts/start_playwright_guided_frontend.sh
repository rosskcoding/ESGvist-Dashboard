#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FRONTEND_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

PORT="${PORT:-3003}"
API_PORT="${API_PORT:-8003}"
NEXT_DIST_DIR="${NEXT_DIST_DIR:-.next-playwright-${PORT}}"

export API_PORT
export NEXT_DIST_DIR

cd "${FRONTEND_DIR}"

# Use a managed dev server for Playwright so regression packs do not depend on a full production build.
exec ./node_modules/.bin/next dev --hostname 127.0.0.1 --port "${PORT}"
