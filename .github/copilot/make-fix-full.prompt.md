#instruction
Run the full repository test suite via Makefile targets (CI-equivalent), diagnose failures, and fix them iteratively with minimal diffs until all checks pass. Include UI unit/component tests and UI→backend e2e.

#environment OFFLINE
- (.venv)
- Offline-first env: export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 HF_HUB_DISABLE_TELEMETRY=1 LX_OFFLINE=1
- Work from repo root. Use Makefile targets as the source of truth. Follow `AGENTS.md` conventions.

#environment ONLINE
- (.venv)
- Offline-first env: export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 HF_HUB_DISABLE_TELEMETRY=1 LX_OFFLINE=0
- Work from repo root. Use Makefile targets as the source of truth. Follow `AGENTS.md` conventions.

#discovery
1) Identify BACKEND “full suite” in this priority order:
   - ci, verify, check, test-all, tests, test
   - If a target named run-ci-mode exists, treat it as an alias of `ci`.
2) Identify UI targets (prefer a single “verify”):
   - Prefer ui-verify; else compose from ui-test (unit/component) + ui-e2e (Playwright).
3) Inspect available targets:
   - make help || true
   - make -qp | sed -n 's/^\([a-zA-Z0-9][a-zA-Z0-9._-]*\):.*/\1/p' | sort -u
4) Record relevant env/ports if present:
   - UI_BASE_URL (default http://localhost:5173)
   - UI_E2E_START_BACKEND, UI_E2E_BACKEND_CMD, UI_E2E_BACKEND_URL
5) Service stop targets (if present): stop-all (graceful), stop-all-force.

#process
Run BACKEND and UI in BOTH environments (OFFLINE first, then ONLINE), reusing the same venv. Keep runs isolated and clean with stop targets.

0) Clean slate (no-op if targets absent)
   - make stop-all || true

A) BACKEND suite
1) Dry-run & execute
   - FULL_TARGET := auto-discovered per #discovery (prefer `ci`)
   - make -n ${FULL_TARGET}
   - make ${FULL_TARGET} 2>&1 | tee .artifacts/backend_${ENV}_run1.log
2) Triage the first blocking error
   - Identify the true root cause.
   - Apply the smallest viable fix (code/tests/config/Makefile), aligned with LoquiLex principles (offline-first, transparency, minimal diffs).
   - Never delete/skip tests to “go green.” No broad refactors.
3) Re-run & iterate until ${FULL_TARGET} exits 0.
4) Gate checks (if not already covered by ${FULL_TARGET}):
   - make lint
   - make fmt-check
   - make typecheck
   - make test -k (only if the suite target didn’t run tests)

B) UI suite
1) UI unit/component + e2e selection
   - If `ui-verify` exists, use it as the UI suite.
   - Else run both `make ui-test` and `make UI_E2E_START_BACKEND=1 ui-e2e`.
2) Ensure server availability for e2e
   - If e2e cannot reach UI_BASE_URL (e.g., ECONNREFUSED), minimally patch Playwright config with a `webServer` (vite “dev” or “preview”) OR add background-start inside the ui-e2e target; choose the smaller, clearer change.
3) Run UI suite
   - make -n ui-verify || true
   - (UI_E2E_START_BACKEND=1) make ui-verify 2>&1 | tee .artifacts/ui_${ENV}_run1.log
   - If `ui-verify` is missing: run the two commands separately and capture logs.
4) Triage/fix
   - For Vitest issues: stabilize selectors, test env (`happy-dom`), or RTL patterns.
   - For Playwright: ensure stable data-testid hooks; align health endpoint path; avoid network calls when OFFLINE; prefer local API_BASE_URL.
   - Keep diffs minimal.
5) Re-run until green.
6) Cleanup
   - make stop-all || true

C) Repeat A and B in the second environment (ONLINE) and ensure both pass.

#constraints
- Maintain offline determinism (no external network) when LX_OFFLINE=1.
- Prefer `anyio`-compatible async usage in tests.
- Keep commit messages imperative; reference ISSUE_REF if provided.
- Use stop targets to avoid orphaned services: prefer `stop-all`; escalate to `stop-all-force` only when necessary.

#deliverable-format
Write ONLY this report to `.github/copilot/current-task-deliverables.md`:
1. Executive Summary — Which BACKEND and UI target(s) ran, failures found, key changes, outcome (OFFLINE vs ONLINE).
2. Steps Taken — Bullet list of commands, diagnoses, and edits (per iteration), clearly separated by OFFLINE and ONLINE runs.
3. Evidence & Verification — Full command outputs for failing→passing runs; relevant diffs/snippets, grouped per environment.
4. Final Results — Explicit pass/fail per environment and any residual warnings/TODOs.
5. Files Changed — Each file + brief reason (tests, impl, Makefile, CI, docs).

#output
- Commit with imperative messages (e.g., `fix(streaming): ensure thread-to-loop handoff on FastAPI loop`), optionally appending ISSUE_REF.

#run
- BACKEND FULL_TARGET: auto-discover using #discovery; prefer `ci` (treat `run-ci-mode` as an alias).
- UI TARGETS: prefer `ui-verify`; else run `ui-test` and `UI_E2E_START_BACKEND=1 ui-e2e`.
- Before each major run and at the very end: `make stop-all || true`.
- ISSUE_REF: <optional>
