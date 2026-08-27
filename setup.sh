#!/usr/bin/env bash
# Setup script for Linux/macOS — creates venv, installs deps, installs browser.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

PYTHON="${PYTHON:-python3}"

if [ ! -d ".venv" ]; then
  echo "[setup] Creating virtualenv (.venv)..."
  "$PYTHON" -m venv .venv
fi

echo "[setup] Installing requirements into .venv..."
.venv/bin/pip install --upgrade pip
.venv/bin/pip install -r requirements.txt

echo "[setup] Installing Chromium browser for patchright..."
.venv/bin/patchright install chromium

echo ""
echo "[setup] Done!"
echo "  Next: copy .secret.example to .secret and fill in your 2captcha key,"
echo "  then run: ./run.sh --target 1000 --parallel 10"
