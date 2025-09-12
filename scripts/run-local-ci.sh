#!/usr/bin/env bash
set -euo pipefail

VENV="${VENV:-.venv}"
export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 HF_HUB_DISABLE_TELEMETRY=1 LOQUILEX_OFFLINE=1

echo "=== Environment (offline flags) ==="
env | grep -E '^(HF_HUB_OFFLINE|TRANSFORMERS_OFFLINE|HF_HUB_DISABLE_TELEMETRY|LOQUILEX_OFFLINE)='

echo "=== Ruff ==="
"$VENV/bin/ruff" check .

echo "=== Black --check ==="
"$VENV/bin/black" --check .

echo "=== MyPy (non-blocking) ==="
( "$VENV/bin/mypy" loquilex || true )

echo "=== Pytest (unit/integration, not e2e) ==="
"$VENV/bin/pytest" -m "not e2e" -vv -rA --maxfail=1 --disable-warnings

echo "=== Pytest (e2e) ==="
"$VENV/bin/pytest" -q --maxfail=1 -m e2e --disable-warnings --no-header --no-summary