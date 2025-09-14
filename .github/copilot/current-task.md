# Task: Purge all `GF_*` environment variables — enforce `LX_*` only (no fallbacks)

**Epic / Issue:** LoquiLex Epic — *Dedupe tooling, remove dead code, and harden test infra* (**Issue #3**)
**PR:** Continue work in **PR #24** (use the existing PR branch; do **not** create a new one)

---

## Objective
Erase the legacy `GF_*` namespace from the project. Enforce `LX_*` as the **only** configuration prefix. Remove any fallback, aliasing, or deprecation logic; update code, scripts, tests, docs, and tooling accordingly. This repo never shipped `GF_*`, so no compatibility layer is required.

---

## Acceptance Criteria

### A) Code & Scripts
- All runtime reads/writes accept **`LX_*` only** (no `GF_*` anywhere; no aliasing; no warnings).
- Central env helpers (e.g., `loquilex/config/env.py`, `scripts/env.py`) provide **LX-only** getters such as `getenv`, `getenv_bool`, `getenv_int` — with **no** legacy aliasing or warnings.
- Any script that referenced `GF_*` is updated to `LX_*` only (delete comments referencing legacy vars). Examples to migrate everywhere:
  - `GF_ASR_MODEL` → `LX_ASR_MODEL`
  - `GF_DEVICE` → `LX_DEVICE`
  - `GF_SAVE_AUDIO_PATH` → `LX_SAVE_AUDIO_PATH`
  - `GF_API_PORT` → `LX_API_PORT`
  - `GF_OUT_DIR` → `LX_OUT_DIR`
  - `GF_ALLOWED_ORIGINS` → `LX_ALLOWED_ORIGINS`
  - `GF_SKIP_MODEL_PREFETCH` → `LX_SKIP_MODEL_PREFETCH`

### B) Tests
- Remove/adjust tests that assert `GF_*` behavior or `DeprecationWarning`s.
- All tests pass using only `LX_*` variables.

### C) Makefile & Tooling (CI / VS Code)
- Makefile help/comments reference only `LX_*`.
- Workflows, scripts, and VS Code tasks use only `LX_*` envs (no `GF_*`).

### D) Docs & Examples
- README, CI-TESTING, `.env.example`, inline comments, and developer docs reference only `LX_*`.
- Add a one-paragraph **Migration note** in PR description: “If you had local `GF_*` envs, rename to `LX_*` (same suffix). This repo never shipped `GF_*` publicly.”

### E) Zero legacy strings
- `git grep -n "\\bGF_"` returns **no matches** across tracked files (source, tests, scripts, docs, tooling).

---

## Non-Goals
- No feature changes beyond env prefix cleanup.
- No new configuration system beyond `LX_*`.
- No unrelated CI refactors.

---

## Plan of Work
1) **Central env helpers:** remove any aliasing (e.g., `*-or-gf` helpers) and deprecation warnings. Keep LX-only getters.
2) **Bulk replace:** mechanically rename `GF_` → `LX_` where appropriate; delete fallback branches.
3) **Purge tests/warnings:** remove tests tied to `GF_*` and all `DeprecationWarning` code paths.
4) **Docs pass:** update README / CI-TESTING / `.env.example` and any comments to `LX_*` only.
5) **Verify** (quality gates + repository grep).

---

## Verification

```bash
# 1) Quality gates
make lint typecheck unit

# 2) Ensure no legacy vars remain
git grep -n "\bGF_" || true   # expect no output

# 3) Minimal dev smoke (offline-first)
make dev-minimal

# 4) Example run with LX_* only (tweak as needed)
LX_API_PORT=8080 LX_OUT_DIR=.artifacts/out LX_ALLOWED_ORIGINS=http://localhost:5173   make run-ci-mode || true
```

**Expected:**
- Lint/type/tests pass.
- `git grep` prints nothing (no `GF_*`).
- No deprecation warnings in test output.
- App/scripts respect `LX_*` only.

---

## Commit / PR Text

- **Primary commit:** `refactor(env): remove GF_*; enforce LX_* only (no fallbacks)`
- **Follow-ups if needed:**
  - `docs(env): update README/CI-TESTING/.env.example to LX_*`
  - `test(env): remove GF_* deprecation tests`

**PR #24 title (update if needed):** `refactor(env): remove GF_*; enforce LX_* only (no fallbacks)`
**PR description addition:** Include the migration note above.
