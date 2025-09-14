#!/usr/bin/env bash
# scripts/ci-gh-parity.sh
# Run the exact same sequence as CI (lint → format → type → unit → e2e), with offline flags.
# Must be executed inside the container with the repo bind-mounted at /app.
set -euo pipefail

cd /app

echo "=== Environment (offline flags) ==="
env | grep -E '^(HF_HUB_OFFLINE|TRANSFORMERS_OFFLINE|HF_HUB_DISABLE_TELEMETRY|LX_OFFLINE)=' || true

echo "=== Python ==="
python --version
pip --version

echo "=== Ruff ==="
ruff check .

echo "=== Black --check ==="
black --check .

echo "=== MyPy (non-blocking, CI-style) ==="
( mypy loquilex || true )

echo "=== Pytest (unit/integration: not e2e) ==="
pytest -m "not e2e" -vv -rA --maxfail=1 --disable-warnings

echo "=== Pytest (e2e) ==="
pytest -q --maxfail=1 -m e2e --disable-warnings --no-header --no-summary

echo "=== DONE: CI-parity run completed successfully ==="
