#!/usr/bin/env bash
set -euo pipefail

VENV="${VENV:-.venv}"
CI_MODE="${CI_MODE:-local}"  # "ci" for lightweight, "local" for full ML deps
export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 HF_HUB_DISABLE_TELEMETRY=1 LOQUILEX_OFFLINE=1

echo "=== Environment (offline flags) ==="
env | grep -E '^(HF_HUB_OFFLINE|TRANSFORMERS_OFFLINE|HF_HUB_DISABLE_TELEMETRY|LOQUILEX_OFFLINE)='
echo "CI_MODE=${CI_MODE} (ci=lightweight, local=full ML deps)"

echo "=== Installing Dependencies ==="
if [[ "$CI_MODE" == "ci" ]]; then
  echo "CI mode: Installing lightweight dependencies only (no heavy ML packages)"
  pip install -r requirements-ci.txt
  [ -f requirements-dev.txt ] && pip install -r requirements-dev.txt || pip install httpx
else
  echo "Local mode: Installing full dependencies including ML packages"
  pip install -r requirements.txt
  [ -f requirements-dev.txt ] && pip install -r requirements-dev.txt
fi

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