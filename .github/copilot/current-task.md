#instruction
Run the full repository test suite via Makefile targets (CI-equivalent), diagnose failures, and fix them iteratively with minimal diffs until all checks pass.

#environment OFFLINE
- (.venv)
- Offline-first env: export HF_HUB_OFFLINE=1, TRANSFORMERS_OFFLINE=1, HF_HUB_DISABLE_TELEMETRY=1, LX_OFFLINE=1
- Work from repo root. Use Makefile targets as the source of truth. Follow `AGENTS.md` conventions.

#environment ONNLINE
- (.venv)
- Offline-first env: export HF_HUB_OFFLINE=1, TRANSFORMERS_OFFLINE=1, HF_HUB_DISABLE_TELEMETRY=1, LX_OFFLINE=0
- Work from repo root. Use Makefile targets as the source of truth. Follow `AGENTS.md` conventions.

#discovery
1) Try to identify the canonical “full suite” target in this priority order:
   - `ci`, `verify`, `check`, `test-all`, `tests`, `test`, `dead-code-anlysis`, `typecheck`, `lint`
2) Use:
   - `make help || true` (if available)
   - `make -qp | sed -n 's/^\([a-zA-Z0-9][a-zA-Z0-9._-]*\):.*/\1/p' | sort -u`
3) If `run-ci-mode` exists, run it first to prep the env.

#process
1) **Dry-run & execute**
   - `make -n <FULL_TARGET>` to preview
   - `make <FULL_TARGET>` and capture full stdout/stderr
2) **Triage first blocking error**
   - Identify true root cause (not just the symptom).
   - Propose and apply the smallest viable fix (code/tests/config) aligned with LoquiLex principles (offline-first, transparency, minimal diffs).
   - Never delete or skip tests to “go green.” No broad refactors.
3) **Re-run & iterate** until `<FULL_TARGET>` exits 0.
4) **Gate checks** (if not already covered by `<FULL_TARGET>`):
   - `make lint`
   - `make typecheck`
   - `make test -k` (only if the suite target didn’t run tests)
5) **CI parity sanity**
   - If the suite target proved incomplete/broken, minimally fix the Makefile target(s) and justify changes.
   - Keep changes tight; no disabling of checks.

#constraints
- Maintain offline determinism (no network in tests).
- Prefer `anyio`-compatible async usage in tests.
- Keep commit messages **imperative**; reference ISSUE_REF if provided.

#deliverable-format
Write **only** this report to `.github/copilot/current-task-deliverables.md`:
1. **Executive Summary** – Which target(s) ran, failures found, key changes, outcome.
2. **Steps Taken** – Bullet list of commands, diagnoses, and edits (per iteration).
3. **Evidence & Verification** – Full command outputs for failing→passing runs; relevant diffs/snippets.
4. **Final Results** – Explicit pass/fail and any residual warnings/TODOs.
5. **Files Changed** – Each file + brief reason (tests, impl, Makefile, CI, docs).

#output
- Commit with imperative messages (e.g., `fix(streaming): ensure thread-to-loop handoff on FastAPI loop`), optionally appending ISSUE_REF.

#run
- FULL_TARGET: (auto-discover using #discovery; prefer `ci` if present)
- ISSUE_REF: 31
