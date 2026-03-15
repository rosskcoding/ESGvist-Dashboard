#!/usr/bin/env bash
set -euo pipefail

export PLAYWRIGHT_BROWSERS_PATH="${PLAYWRIGHT_BROWSERS_PATH:-/ms-playwright}"

fix_runtime_dir() {
  local dir="$1"
  mkdir -p "$dir" 2>/dev/null || true
  chown -R appuser:appuser "$dir" 2>/dev/null || true
  chmod -R u+rwX "$dir" 2>/dev/null || true
}

# Ensure runtime directories are writable regardless of host UID/GID.
fix_runtime_dir "/app/builds"
fix_runtime_dir "/app/uploads"
fix_runtime_dir "$PLAYWRIGHT_BROWSERS_PATH"

# Check if directory is writable
if [ ! -w "$PLAYWRIGHT_BROWSERS_PATH" ]; then
  echo "[export-worker] WARNING: $PLAYWRIGHT_BROWSERS_PATH is not writable, falling back to ~/.cache/ms-playwright"
  export PLAYWRIGHT_BROWSERS_PATH="$HOME/.cache/ms-playwright"
  fix_runtime_dir "$PLAYWRIGHT_BROWSERS_PATH"
fi

echo "[export-worker] Using PLAYWRIGHT_BROWSERS_PATH=$PLAYWRIGHT_BROWSERS_PATH"

# If Chromium is not installed yet, install it.
# Check for both chromium- and chromium_headless_shell- directories
if ! ls -1 "$PLAYWRIGHT_BROWSERS_PATH" 2>/dev/null | grep -qE '^chromium'; then
  echo "[export-worker] Playwright Chromium not found in $PLAYWRIGHT_BROWSERS_PATH; installing..."
  su appuser -s /bin/bash -c "PLAYWRIGHT_BROWSERS_PATH='$PLAYWRIGHT_BROWSERS_PATH' python -m playwright install chromium"
else
  echo "[export-worker] Playwright Chromium already present in $PLAYWRIGHT_BROWSERS_PATH"
fi

cmd=""
for arg in "$@"; do
  if [[ -z "$cmd" ]]; then
    cmd="$(printf '%q' "$arg")"
  else
    cmd="$cmd $(printf '%q' "$arg")"
  fi
done

exec su appuser -s /bin/bash -c "cd /app && PLAYWRIGHT_BROWSERS_PATH='$PLAYWRIGHT_BROWSERS_PATH' $cmd"


