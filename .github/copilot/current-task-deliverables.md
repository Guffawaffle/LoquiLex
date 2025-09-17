## Executive Summary
- Implemented SPA fallback for deep routes while preserving API/WS/static. Mounted `ui/app/dist/assets` at `/assets`, added explicit `/` index route, and a catch-all GET/HEAD fallback that returns `index.html` unless path starts with `/api`, `/ws`, or `/assets`. Added `/api/health` (GET + HEAD). Outcome: deep routes like `/settings` return 200 HTML; `/api/health` returns API JSON; assets serve correctly; no `vite.svg` references.

## Steps Taken
- 2025-09-17 03:55: Ran unit tests to validate baseline (git: `$(git rev-parse --short HEAD)`)
- 2025-09-17 03:58: Edited `loquilex/api/server.py` to add `/api/health`, tighten SPA fallback guardrails, and mount assets plus index route.
- 2025-09-17 04:05: Lint/typecheck/tests via `make lint && make typecheck && make unit` (all green).
- 2025-09-17 04:10: Started uvicorn and validated endpoints with individual curls.
- 2025-09-17 04:14: Re-validated after adding explicit HEAD for `/api/health` and restarting server.

## Evidence & Verification
- Command environment: Linux (bash). Python: from venv. Local run (not CI).

- Lint/typecheck/tests:
  - ruff: All checks passed
  - mypy: Success: no issues found in 45 files
  - pytest: 167 passed, 4 skipped, 20 warnings

- Headers for `/settings` (SPA fallback):
  HTTP/1.1 200 OK
  content-type: text/html; charset=utf-8

- `/api/health` HEAD and GET:
  - HEAD: HTTP/1.1 200 OK
  - GET: HTTP/1.1 200 OK with body {"status":"ok"}

- Asset under `/assets/<file>`:
  HTTP/1.1 200 OK
  content-type: text/javascript; charset=utf-8

- No vite.svg references:
  grep -RIn "vite.svg" ui/app/index.html ui/app/dist/index.html → no matches

- Diffs (key excerpts):
  - Added:
    - `@app.get("/api/health")` and `@app.head("/api/health")`
    - Mount `/assets` from `ui/app/dist/assets`
    - Root `@app.get("/")/@app.head("/")` serving `index.html`
    - SPA fallback `@app.get/@app.head("/{full_path:path}")` with guardrails for `api/`, `ws/`, `assets/`

## Final Results
- Pass: All acceptance criteria met:
  - GET `/settings` → 200 text/html
  - GET/HEAD `/api/health` → API JSON/200 (not HTML)
  - WS unchanged (not exercised here; routes remain under `/ws`)
  - Assets under `/assets/<built-file>` → 200 correct type
  - No `vite.svg` in source or dist index.html

## Files Changed
- `loquilex/api/server.py`: Serve assets at `/assets`, add root index route, add GET/HEAD `/api/health`, and SPA fallback with guardrails.