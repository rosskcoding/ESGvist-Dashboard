#!/usr/bin/env bash
set -euo pipefail

PORT="${1:-8000}"

echo "Starting local server on http://localhost:${PORT}/"
echo "Press Ctrl+C to stop."

python3 -m http.server "${PORT}"

