#!/usr/bin/env bash
set -euo pipefail

echo "=== Environment (offline flags) ==="
env | grep -E '^(HF_HUB_OFFLINE|TRANSFORMERS_OFFLINE|HF_HUB_DISABLE_TELEMETRY|LX_OFFLINE)=' || true

echo "=== Ruff ==="
ruff check .

echo "=== Black --check ==="
black --check .

echo "=== MyPy (non-blocking) ==="
( mypy loquilex || true )

echo "=== Pytest (unit/integration, not e2e) ==="
pytest -m "not e2e" -vv -rA --maxfail=1 --disable-warnings

echo "=== Pytest (e2e) ==="
pytest -q --maxfail=1 -m e2e --disable-warnings --no-header --no-summary
