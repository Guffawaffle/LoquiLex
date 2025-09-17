#instruction
Unify the WebSocket path and keep the API surface clean with minimal diffs.

## Do exactly this
1) **Frontend**
   - Centralize WS path via **build-time config**: `VITE_WS_PATH` (default `/ws`).
   - Replace all hardcoded `/events` usages in `ui/app/src` with a helper that builds `ws://<origin><VITE_WS_PATH>/{sid}`.
   - Do **not** mount downloads under the WS path; leave HTTP downloads under `/api/…` (no change if not applicable).

2) **Backend**
   - Keep default `WS_PATH=/ws`.
   - Add **optional alias** for `/events` behind env `LX_WS_ALLOW_EVENTS_ALIAS=1` (dev-only). Log a deprecation warning when used.
   - **CSP (prod):** `connect-src 'self' ws://127.0.0.1:*;` (scope scheme to loopback). Dev gating can remain broader.

3) **Tests / Evidence**
   - e2e/integration: assert WS handshake succeeds using configured path.
   - Deliverables must include:
     - Real header lines: `Content-Security-Policy`, `Permissions-Policy` (prod & dev runs).
     - Real asset header checks: `/vite.svg` and one file under `/assets/*` with content-type.
     - `grep` proving no leftover `/events` in UI sources (except comments/tests), and that UI reads `VITE_WS_PATH`.

## Acceptance Criteria
- Canonical WS base is `/ws`; frontend reads `VITE_WS_PATH` (default `/ws`).
- Optional `/events` alias works only when `LX_WS_ALLOW_EVENTS_ALIAS=1` and logs a deprecation warning.
- No remaining hardcoded `/events` in UI (except tests/comments).
- CSP prod uses `connect-src 'self' ws://127.0.0.1:*;` (no global `ws:`).
- e2e WS handshake passes against FastAPI-served build.
- All CI/lint/type/test pass; diffs minimal.

#requirements
- One branch: `copilot/fix-58-ws-path`.
- Follow `AGENTS.md` (offline-first, minimal diffs, imperative commits).
- Reuse existing patterns; no new dependencies.
- Use `npm ci` for UI; Node 20 LTS only.
- If ambiguity: search repo for existing helpers before adding new ones.

#deliverable-format
Write `.github/copilot/current-task-deliverables.md` with:
1. **Executive Summary** (what changed, why, outcome).
2. **Steps Taken** (timestamps, commands, files edited).
3. **Evidence & Verification**:
   - Header dumps (prod/dev) for CSP/Permissions-Policy.
   - `curl -I` for `/vite.svg` + one concrete `/assets/<file>` with content-type.
   - `grep` outputs proving `VITE_WS_PATH` usage and no leftover `/events`.
   - e2e WS handshake result (pass/fail).
4. **Final Results** (pass/fail, follow-ups).
5. **Files Changed** (each file + purpose).

#output
Write only the deliverables file into `.github/copilot/current-task-deliverables.md`.
