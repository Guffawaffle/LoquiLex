#!/usr/bin/env bash
set -euo pipefail
echo ">> Running UI E2E tests (Playwright) against ${UI_BASE_URL:-http://localhost:5173}"
if [[ "${LX_OFFLINE:-}" == "1" ]]; then
  echo ">> LX_OFFLINE=1: skipping Playwright browser launch (offline mode)"
  exit 0
fi
backend_pid=""
cleanup() {
  if [[ -n "${backend_pid}" ]]; then kill "${backend_pid}" 2>/dev/null || true; fi
}
trap cleanup EXIT
if [[ "${UI_E2E_START_BACKEND:-1}" == "1" ]]; then
  echo ">> Starting backend: ${UI_E2E_BACKEND_CMD:-python -m loquilex.api.server --host 127.0.0.1 --port 8000}"
  bash -lc "${UI_E2E_BACKEND_CMD:-python -m loquilex.api.server --host 127.0.0.1 --port 8000}" >/tmp/ui-e2e-backend.log 2>&1 &
  backend_pid=$!
  echo ${backend_pid} > .backend.pid
  sleep 3
fi
cd ui
if [[ "${LX_OFFLINE:-1}" != "1" ]]; then
  echo ">> Installing Playwright Chromium browser (online mode)"
  PLAYWRIGHT_BROWSERS_PATH="${PLAYWRIGHT_BROWSERS_PATH:-0}" npx playwright install chromium --with-deps >/dev/null 2>&1 || true
fi
BASE_URL="${UI_BASE_URL:-http://localhost:5173}" API_BASE_URL="${UI_E2E_BACKEND_URL:-http://127.0.0.1:8000}" \
  npm run e2e
