#!/usr/bin/env bash
#
# dead-code-analysis.sh — Comprehensive dead code detection
# Works both locally (.venv) and inside Docker CI (/opt/venv).

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

# Resolve Python interpreter (container or local)
VENV_PY="${VENV_PY:-}"
if [[ -z "${VENV_PY}" ]]; then
  if [[ -x "/opt/venv/bin/python" ]]; then
    VENV_PY="/opt/venv/bin/python"
  elif [[ -x ".venv/bin/python" ]]; then
    VENV_PY=".venv/bin/python"
  else
    VENV_PY="$(command -v python || command -v python3)"
  fi
fi
echo "Using Python: ${VENV_PY}"

REPORTS_DIR=".artifacts/dead-code-reports"
mkdir -p "${REPORTS_DIR}"

echo "=== Dead Code Analysis Report ===" | tee "$REPORTS_DIR/summary.md"
echo "Generated: $(date)" | tee -a "$REPORTS_DIR/summary.md"
echo "" | tee -a "$REPORTS_DIR/summary.md"

## 1) Ruff — unused imports/variables/arguments
echo "## 1. Ruff Analysis (unused imports/variables/arguments)" | tee -a "${REPORTS_DIR}/summary.md"
echo "" | tee -a "${REPORTS_DIR}/summary.md"
if "${VENV_PY}" -m ruff check loquilex tests 2>&1 | tee "${REPORTS_DIR}/ruff-unused.txt"; then
  echo "" | tee -a "${REPORTS_DIR}/summary.md"
  echo "No unused code detected by Ruff" | tee -a "${REPORTS_DIR}/summary.md"
else
  echo "" | tee -a "${REPORTS_DIR}/summary.md"
  echo "⚠️  Unused code detected by Ruff:" | tee -a "${REPORTS_DIR}/summary.md"
  echo '```' | tee -a "${REPORTS_DIR}/summary.md"
  cat "${REPORTS_DIR}/ruff-unused.txt" | tee -a "${REPORTS_DIR}/summary.md"
  echo '```' | tee -a "${REPORTS_DIR}/summary.md"
fi
echo "" | tee -a "${REPORTS_DIR}/summary.md"

## 2) Vulture — dead code detection
echo "## 2. Vulture Analysis (dead code detection, min-confidence 70%)" | tee -a "${REPORTS_DIR}/summary.md"
echo "" | tee -a "${REPORTS_DIR}/summary.md"
if "${VENV_PY}" -m vulture loquilex --min-confidence 70 2>&1 | tee "${REPORTS_DIR}/vulture-deadcode.txt"; then
  echo "" | tee -a "${REPORTS_DIR}/summary.md"
  echo "No dead code detected by Vulture" | tee -a "${REPORTS_DIR}/summary.md"
else
  echo "" | tee -a "${REPORTS_DIR}/summary.md"
  echo "⚠️  Dead code detected by Vulture:" | tee -a "${REPORTS_DIR}/summary.md"
  echo '```' | tee -a "${REPORTS_DIR}/summary.md"
  cat "${REPORTS_DIR}/vulture-deadcode.txt" | tee -a "${REPORTS_DIR}/summary.md"
  echo '```' | tee -a "${REPORTS_DIR}/summary.md"
fi
echo "" | tee -a "${REPORTS_DIR}/summary.md"

## 3) Coverage (optional if config exists)
echo "## 3. Coverage Analysis (if configured)" | tee -a "${REPORTS_DIR}/summary.md"
echo "" | tee -a "${REPORTS_DIR}/summary.md"
if [[ -f "pyproject.toml" || -f ".coveragerc" ]]; then
  "${VENV_PY}" -m coverage erase || true
  if "${VENV_PY}" -m coverage run -m pytest -q 2>&1 | tee "${REPORTS_DIR}/coverage-run.txt"; then
    :
  else
    echo "⚠️  coverage run reported errors (see coverage-run.txt)" | tee -a "${REPORTS_DIR}/summary.md"
  fi
  "${VENV_PY}" -m coverage report 2>&1 | tee "${REPORTS_DIR}/coverage-report.txt" || true
else
  echo "Coverage config not found; skipping." | tee -a "${REPORTS_DIR}/summary.md"
fi

echo "" | tee -a "${REPORTS_DIR}/summary.md"
echo "## 4. Summary & Recommendations" | tee -a "${REPORTS_DIR}/summary.md"
echo "See individual tool outputs in ${REPORTS_DIR}." | tee -a "${REPORTS_DIR}/summary.md"