#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FRONTEND_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

PORT="${PORT:-3003}"
API_PORT="${API_PORT:-8003}"

export API_PORT

cd "${FRONTEND_DIR}"

# Build once for a stable regression surface, then serve it on the managed Playwright port.
./node_modules/.bin/next build

exec ./node_modules/.bin/next start --hostname 127.0.0.1 --port "${PORT}"
