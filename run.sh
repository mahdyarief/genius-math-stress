#!/usr/bin/env bash
# Launcher for the Indonesia Open batch runner.
# Always boots under the project venv (which has patchright), so instances
# spawned via sys.executable inherit the correct interpreter.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PY="$SCRIPT_DIR/.venv/bin/python"

if [ ! -x "$PY" ]; then
  echo "Error: venv python not found at $PY" >&2
  exit 1
fi

exec "$PY" -u "$SCRIPT_DIR/run_batch_indo_open.py" "$@"
