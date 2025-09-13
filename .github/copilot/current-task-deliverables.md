# Task Deliverables: Docs refresh — default to `make dev-minimal` and add `LX_SKIP_MODEL_PREFETCH`

## Executive Summary
We made the lightweight, offline-first workflow the default. `make dev-minimal` now **never** prefetches models and installs only non‑ML dev deps. We documented and hardened `LX_SKIP_MODEL_PREFETCH` (truthy set: `1/true/yes/on`), updated `README.md` and `CI-TESTING.md`, and added a robust guard in `scripts/dev_fetch_models.py`. Local checks (lint, typecheck, unit tests) passed.

## Steps Taken
- **README.md**
  - Promoted `make dev-minimal` to Quickstart and added `run-ci-mode` for parity.
  - Added an “Offline-first Development” section and a small environment flag table.
- **CI-TESTING.md**
  - Documented `LX_SKIP_MODEL_PREFETCH` and how targets respect it.
- **Makefile**
  - Changed `dev-minimal` to **skip any model prefetch** and install non‑ML dev deps.
- **scripts/dev_fetch_models.py**
  - Replaced `exit()` with `sys.exit(0)` and added a boolean-safe truthiness check.
- (Non-blocking) Confirmed `.github/copilot/main.prompt.md` replaces the old `main-prompt.md` without breaking references.

## Evidence & Verification

### Commands Executed
```bash
make lint typecheck unit
```

### Outputs
- **Linting (ruff):** All checks passed.
- **Type Checking (mypy):** No issues found in 22 source files.
- **Unit Tests (pytest):** 26 tests passed. 8 warnings related to legacy `GF_*` env vars (expected during migration).

### Flag behavior checks
```bash
# Script-level skip
LX_SKIP_MODEL_PREFETCH=1 python scripts/dev_fetch_models.py
# → [dev] LX_SKIP_MODEL_PREFETCH set — skipping model prefetch.

# Makefile path verifies no prefetch in dev-minimal (offline-first)
make dev-minimal
# → [dev-minimal] Skipping model prefetch (offline-first).
# → [dev-minimal] Development environment ready.
```

## Final Results
- All acceptance criteria met:
  - `dev-minimal` is default and **never** prefetches.
  - `LX_SKIP_MODEL_PREFETCH` documented and enforced.
  - Docs updated, guard hardened, local checks pass.
- Follow-up: plan a separate task to finish migrating from `GF_*` to `LX_*` envs and remove deprecation warnings.

## Files Changed
1. `README.md` — Quickstart updated; offline-first docs + env table.
2. `CI-TESTING.md` — Offline-first + target behavior documented.
3. `Makefile` — `dev-minimal` no longer prefetches; installs non‑ML dev deps.
4. `scripts/dev_fetch_models.py` — Truthiness guard hardened; `sys.exit(0)`.
