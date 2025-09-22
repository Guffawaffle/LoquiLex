---
mode: 'agent'
model: GPT-5
description: 'Run the full Makefile test suite in offline/online modes and fix failures until all checks pass.'
---

#instruction
Run the full repository test suite via Makefile targets (CI-equivalent), diagnose failures, and fix them iteratively with minimal diffs until all checks pass.

#environment OFFLINE
- (.venv)
- Offline-first env: export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 HF_HUB_DISABLE_TELEMETRY=1 LX_OFFLINE=1
- Work from repo root. Use Makefile targets as the source of truth. Follow `AGENTS.md` conventions.

#environment ONLINE
- (.venv)
- Offline-first env: export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 HF_HUB_DISABLE_TELEMETRY=1 LX_OFFLINE=0
- Work from repo root. Use Makefile targets as the source of truth. Follow `AGENTS.md` conventions.

#discovery
1) Identify the canonical “full suite” target in this priority order:
   - ci, run-ci-mode, test, unit, e2e, test-e2e
2) Inspect available targets:
   - make help || true
   - make -qp | sed -n 's/^\([a-zA-Z0-9][a-zA-Z0-9._-]*\):.*/\1/p' | sort -u
3) If a target named run-ci-mode exists, treat it as an alias of `ci` when selecting FULL_TARGET (do not run it separately “first”).

#process
Run the suite in BOTH environments (OFFLINE first, then ONLINE), reusing the same venv.
1) Dry-run & execute
   - make -n <FULL_TARGET> to preview
   - make <FULL_TARGET> and capture full stdout/stderr
2) Triage the first blocking error
   - Identify the true root cause (not just the symptom).
   - Apply the smallest viable fix (code/tests/config) aligned with LoquiLex principles (offline-first, transparency, minimal diffs).
   - Never delete or skip tests to “go green.” No broad refactors.
3) Re-run & iterate until <FULL_TARGET> exits 0 in the current environment.
4) Repeat steps 1–3 in the second environment and ensure it also exits 0.
5) Gate checks (if not already covered by <FULL_TARGET>):
   - make lint
   - make fmt-check
   - make typecheck
   - make test -k (only if the suite target didn’t run tests)
6) CI parity sanity
   - If the suite target is incomplete/broken, minimally fix the Makefile target(s) and justify changes.
   - Keep changes tight; do not reintroduce removed checks.

#constraints
- Maintain offline determinism (no network in tests) when LX_OFFLINE=1.
- Prefer `anyio`-compatible async usage in tests.
- Keep commit messages imperative; reference ISSUE_REF if provided.

#deliverable-format
Write ONLY this report to `.github/copilot/current-task-deliverables.md`:
1. Executive Summary — Which target(s) ran, failures found, key changes, outcome (OFFLINE vs ONLINE).
2. Steps Taken — Bullet list of commands, diagnoses, and edits (per iteration), clearly separated by OFFLINE and ONLINE runs.
3. Evidence & Verification — Full command outputs for failing→passing runs; relevant diffs/snippets, grouped per environment.
4. Final Results — Explicit pass/fail per environment and any residual warnings/TODOs.
5. Files Changed — Each file + brief reason (tests, impl, Makefile, CI, docs).

#output
- Commit with imperative messages (e.g., `fix(streaming): ensure thread-to-loop handoff on FastAPI loop`), optionally appending ISSUE_REF.

#run
- FULL_TARGET: auto-discover using #discovery; prefer `ci` if present (treat `run-ci-mode` as an alias).
- ISSUE_REF: 31
