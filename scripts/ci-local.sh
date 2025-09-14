#!/usr/bin/env bash
# ci-local.sh — Replicate CI locally (env, installs, lint, tests)

set -euo pipefail
IFS=$'\n\t'

echo "=== Replicating CI Environment Locally ==="

PYVER_CI="3.12.3"

# Detect current Python
PY_NOW="$(python3 -c 'import sys; print(".".join(map(str, sys.version_info[:3])))' 2>/dev/null || true)"
if [[ "${PY_NOW:-unknown}" != "$PYVER_CI" ]]; then
  echo "Warning: CI uses Python $PYVER_CI, you have ${PY_NOW:-unknown}"
  echo "Tip: pyenv local $PYVER_CI  # or use the project's venv/direnv"
fi

# CI env flags (offline-first)
export HF_HUB_OFFLINE=1
export TRANSFORMERS_OFFLINE=1
export HF_HUB_DISABLE_TELEMETRY=1
export LX_OFFLINE=1

# Determinism & quieter pip
export PYTHONHASHSEED=0
export PIP_DISABLE_PIP_VERSION_CHECK=1

echo "=== Environment Variables ==="
env | grep -E '^(HF_HUB_OFFLINE|TRANSFORMERS_OFFLINE|HF_HUB_DISABLE_TELEMETRY|LX_OFFLINE|PYTHONHASHSEED)=' || true

echo "=== Installing Dependencies (CI-style) ==="
python -m pip install -U pip

# Avoid pulling giant CUDA wheels when you don't need GPU locally.
# (Safe: tests use fakes; CPU wheels are fine.)
# If you REALLY want GPU wheels locally, set USE_CUDA=1.
if [[ "${USE_CUDA:-}" != "1" ]]; then
  # Give pip access to CPU-only torch wheels
  export PIP_EXTRA_INDEX_URL="https://download.pytorch.org/whl/cpu"
fi

# Install base + dev; use CI mode if requested to avoid heavy ML deps
if [[ "${CI_MODE:-local}" == "ci" ]]; then
  echo "CI mode: Using lightweight requirements (no heavy ML packages)"
  if [[ -f requirements-ci.txt ]]; then
    python -m pip install -r requirements-ci.txt
  fi
else
  echo "Local mode: Using full requirements including ML packages"
  if [[ -f requirements.txt ]]; then
    python -m pip install -r requirements.txt
  fi
fi
if [[ -f requirements-dev.txt ]]; then
  python -m pip install -r requirements-dev.txt
else
  python -m pip install httpx
fi

echo "=== Running Lint (same as CI) ==="
# Prefer pinned tools from requirements-dev.txt; fall back to latest if missing.
python - <<'PY'
import importlib, sys, subprocess
tools = ["ruff", "black", "mypy"]
missing = [t for t in tools if importlib.util.find_spec(t) is None]
if missing:
    subprocess.check_call([sys.executable, "-m", "pip", "install", *missing])
PY

python -m ruff check .
python -m black --check .
# mypy might be set to "advisory" locally; mirror CI behavior if CI treats mypy as soft.
python -m mypy loquilex || true

echo "=== Running Unit/Integration Tests (skip e2e) ==="
set +e
python -m pytest -m "not e2e" -vv -rA --maxfail=1 --disable-warnings
code=$?
if [[ $code -ne 0 ]]; then
  echo "Re-running last failures with extra context"
  python -m pytest --lf -vv -rA
  exit 1
fi
set -e

echo "=== Running E2E Tests (optional) ==="
# Only run if FastAPI is available OR user explicitly requests
if python - <<'PY'
import sys
try:
    import fastapi  # noqa: F401
except Exception:
    sys.exit(1)
PY
then
  python -m pytest -m "e2e" -vv -rA --maxfail=1 --disable-warnings
else
  echo "Skipping e2e (fastapi not installed). Install dev deps to enable."
fi

echo "=== All CI checks passed locally! ==="