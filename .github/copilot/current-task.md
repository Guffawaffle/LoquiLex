# Task: Scripts de-dupe — centralize model prefetch & env detection; delete dead scripts (Epic #3 — Step 5)

**Epic:** Dedupe tooling, remove dead code, and harden test infra.
**Focus item:** 5) Scripts de-dupe: centralize model prefetch/env detection; delete dead scripts.
**Branch:** `epic3/scripts-dedupe`

---

## Objective
Create a single, reusable source of truth for environment handling and model prefetch gating, then migrate script call-sites to it and remove obsolete scripts. Preserve offline-first behavior: **no prefetch unless explicitly invoked**, and fully honor `LX_SKIP_MODEL_PREFETCH` (with legacy `GF_*` deprecation warnings).

---

## Acceptance Criteria
- **New shared helpers (Python):**
  - `scripts/env.py` exposes:
    - `is_truthy(str|None) -> bool` (1/true/yes/on, case-insensitive)
    - `getenv(name, default=None, aliases=())` that prefers `LX_*`, then checks legacy `GF_*`, emitting a one-time `DeprecationWarning` when a legacy var is used.
    - `getenv_bool(name, default=False, aliases=())` built atop `getenv` + `is_truthy`.
  - `scripts/models.py` exposes:
    - `should_skip_prefetch() -> bool` (reads `LX_SKIP_MODEL_PREFETCH` via `getenv_bool`)
    - `prefetch_asr(model: str, download_root: Path) -> None` stub that **bails fast** if `should_skip_prefetch()`.
    - A tiny `main()` so `python -m scripts.models prefetch-asr` works (no-ops when skipping).
- **Migrations:**
  - `scripts/dev_fetch_models.py` imports from `scripts.env`/`scripts.models` and defers skip logic to the shared helpers.
  - Makefile targets that call prefetch scripts remain functionally identical; when the skip flag is set, they log and return success.
- **Dead code removed:** Any duplicate env/prefetch helpers or unused scripts are deleted.
- **Docs:** `CI-TESTING.md` gains a 2–3 line note that env/prefetch logic is centralized in `scripts/env.py` and `scripts/models.py`.
- **Tests:** At least unit tests for `is_truthy` and `getenv*_` mapping (GF_* → LX_* deprecation).
- **Verification:** Commands below complete successfully (including offline paths).

---

## Planned Changes

1) **Add shared helpers**
   - `scripts/env.py` and `scripts/models.py` per above.
   - `scripts/__init__.py` (empty) to allow `python -m scripts.models`.

2) **Migrate current scripts**
   - Update `scripts/dev_fetch_models.py` to:
     - import `should_skip_prefetch` from `scripts.models`,
     - exit 0 early if skipping,
     - otherwise call `prefetch_asr(...)` (stub remains a no-op for now).

3) **Audit & delete dead scripts**
   - Run `git ls-files scripts/` and classify:
     - **Keep & migrate** to shared helpers.
     - **Delete** (old sh/py fetchers, obsolete env toggles, etc.).
   - Remove deleted scripts from Makefile and docs.

4) **Docs & tests**
   - `CI-TESTING.md` short note about the new central helpers.
   - Add `tests/test_env_helpers.py` for `is_truthy`, `getenv`, `getenv_bool` with GF_* → LX_* fallback + deprecation.

---

## Verification Steps

```bash
# 0) Safety: fresh venv and offline path
make dev-minimal

# 1) Unit tests for env helpers (add under tests/)
pytest -q tests/test_env_helpers.py

# 2) Skip behavior (offline)
LX_SKIP_MODEL_PREFETCH=1 python -m scripts.models prefetch-asr --model tiny.en
LX_SKIP_MODEL_PREFETCH=1 python scripts/dev_fetch_models.py

# 3) Non-skip path (online optional; should no-op safely if not implemented)
python -m scripts.models prefetch-asr --model tiny.en || true

# 4) Makefile call sites still succeed (no downloads when flag set)
LX_SKIP_MODEL_PREFETCH=1 make dev
```

---

## Commit message (example)

```
chore(scripts): centralize env + prefetch logic; migrate dev_fetch_models; remove dead helpers
```

## Out of Scope
- Changing actual model download implementation (stub stays minimal for now).
- GPU enablement toggles or ML dependency changes (tracked elsewhere in Epic #3).
- CI workflow edits (beyond doc note and unit tests).
