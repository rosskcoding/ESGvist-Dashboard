#!/usr/bin/env bash
set -euo pipefail

fix_runtime_dir() {
  local dir="$1"
  mkdir -p "$dir"
  # Best-effort ownership fix for named volumes that may be created as root.
  chown -R appuser:appuser "$dir" 2>/dev/null || true
  chmod -R u+rwX "$dir" 2>/dev/null || true
}

fix_runtime_dir "/app/builds"
fix_runtime_dir "/app/uploads"

cmd=""
for arg in "$@"; do
  if [[ -z "$cmd" ]]; then
    cmd="$(printf '%q' "$arg")"
  else
    cmd="$cmd $(printf '%q' "$arg")"
  fi
done

exec su appuser -s /bin/bash -c "cd /app && $cmd"
