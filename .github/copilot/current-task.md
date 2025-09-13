
# Task: Docs refresh — default to `make dev-minimal` and add `LX_SKIP_MODEL_PREFETCH` (Epic)

**Source:** Epic “Dedupe tooling, remove dead code, and harden test infra.”
Focus on Epic checklist item **2)** (Docs/book: switch dev setup to `make dev-minimal`; add opt-ins & `LX_SKIP_MODEL_PREFETCH`).

---

## Objective

Make the lightweight, offline-first developer workflow the primary path. Update docs to default to `make dev-minimal`, provide optional ML paths, and introduce an explicit environment flag `LX_SKIP_MODEL_PREFETCH` that prevents any model downloads during setup. Ensure the Makefile and helper script(s) honor the flag.

One PR = One Chat. Keep scope tight to **docs + minimal glue**. No CI changes in this PR.

---

## Acceptance Criteria

- **README.md**
  - Quickstart shows `make dev-minimal` as the default path.
  - Clearly documents optional ML paths (brief mention) and defers details to `CI-TESTING.md`.
  - Adds a short “Offline-first” note and documents `LX_SKIP_MODEL_PREFETCH=1`.

- **CI-TESTING.md**
  - Mentions `make run-ci-mode` (lightweight) and `make run-local-ci` (full), and how `LX_SKIP_MODEL_PREFETCH` interacts with local dev.
  - States that model prefetch is **opt-in** and should be skipped when the flag is set.

- **Makefile**
  - If `dev-minimal` target is missing, add it. It must:
    - Create/activate venv.
    - Install **non-ML** base + dev dependencies.
    - **Not** prefetch models.
  - Ensure any dev setup that runs a prefetch script only does so when `LX_SKIP_MODEL_PREFETCH` is **unset** (or explicitly `0/false`).

- **scripts/**
  - If a model prefetch script exists (e.g., `scripts/dev_fetch_models.py`), gate it behind `LX_SKIP_MODEL_PREFETCH`. If it does not exist, create a tiny, offline-safe guard that bails when the flag is set.
  - The guard should treat the following as “true”: `1`, `true`, `yes`, `on` (case-insensitive). Anything else is false.

- **No code path should hard-fail** if the flag is set; prefetch is simply skipped with a clear log line.

- **Docs & Makefile tested locally** via the verification steps below.

---

## Constraints & Conventions

- Commit messages: **imperative mood** (e.g., “Update README to default to make dev-minimal”).
- Do **not** edit CI workflows in this PR.
- Offline-first: Assume no network access during `make dev-minimal`.
- Keep diffs tight; prefer surgical edits over rewrites.

---

## Planned Changes

### 1) README.md (Quickstart & Env)

- Replace the current Quickstart section with a minimal path:

```md
## Quickstart (lightweight, offline-first)

```bash
# Minimal dev (no ML downloads, fastest path)
make dev-minimal

# Run the fast, lightweight checks (matches CI's lightweight mode)
make run-ci-mode
```

### Optional (full local CI with ML deps)
```bash
# Brings in ML dependencies and runs the full stack locally
make run-local-ci
```

**Offline-first:** Set `LX_SKIP_MODEL_PREFETCH=1` to prevent any model downloads that helper scripts might attempt.
```

- Add a short table listing relevant env flags (keep it brief, link longer details to CI-TESTING.md):

```md
| Variable                | Purpose                                   | Default |
|-------------------------|-------------------------------------------|---------|
| LX_SKIP_MODEL_PREFETCH  | Skip any model prefetch during dev setup  | unset   |
```

- Keep the existing `LX_*` vs `GF_*` migration note intact.

### 2) CI-TESTING.md

Add/adjust sections to describe:

- `make run-ci-mode` vs `make run-local-ci` and when to use each.
- How `LX_SKIP_MODEL_PREFETCH=1` interacts with helper scripts (no model downloads).
- A short “Verification” recipe (see below).

### 3) Makefile

- Add a `dev-minimal` target if missing. Pseudocode:

```make
.PHONY: dev-minimal
dev-minimal:
	python -m venv .venv
	. .venv/bin/activate; pip install -U pip
	# Install base + dev deps only (no ML)
	. .venv/bin/activate; pip install -r requirements-dev.txt -c constraints.txt
	@echo "Dev (minimal) ready. Models will NOT be prefetched. Use LX_SKIP_MODEL_PREFETCH=1 to enforce."
```

- Wherever model prefetch might be called (e.g., `dev` or `dev-ml` targets), ensure it is gated, for example:

```make
ifneq ($(shell echo $${LX_SKIP_MODEL_PREFETCH:-0} | tr '[:upper:]' '[:lower:]'),1)
# or equivalent case-insensitive check executed in the shell
	. .venv/bin/activate; python scripts/dev_fetch_models.py || true
else
	@echo "LX_SKIP_MODEL_PREFETCH set — skipping model prefetch."
endif
```

### 4) scripts/dev_fetch_models.py (or new guard script)

Implement a tiny guard at the top:

```python
import os, sys

def _istrue(v: str | None) -> bool:
    if v is None:
        return False
    return v.strip().lower() in {"1", "true", "yes", "on"}

if _istrue(os.getenv("LX_SKIP_MODEL_PREFETCH")):
    print("LX_SKIP_MODEL_PREFETCH set — skipping model prefetch.")
    sys.exit(0)

# existing (or placeholder) logic continues here...
```

If there is no existing script, create this file with only the guard plus a friendly message like “No prefetch actions defined; nothing to do.” so calls are idempotent and harmless.

---

## Verification Steps (local)

```bash
# 1) Fresh clone, no network (simulate) — ensure minimal dev works
make dev-minimal

# 2) Ensure fast checks pass
make run-ci-mode

# 3) Confirm flag behavior
LX_SKIP_MODEL_PREFETCH=1 make dev           # Should not attempt any downloads
LX_SKIP_MODEL_PREFETCH=1 python scripts/dev_fetch_models.py  # Script should exit 0 with a skip message

# 4) Full stack (optional, with network)
make run-local-ci
```

---

## Deliverables

- `README.md` and `CI-TESTING.md` updated.
- `Makefile` updated to include (or preserve) `dev-minimal` without model prefetch.
- `scripts/dev_fetch_models.py` (existing or new) honors `LX_SKIP_MODEL_PREFETCH` flag.
- A concise CHANGELOG entry under “Unreleased → Added/Changed”.

---

## PR Title (example)

```
docs(dev): default to `make dev-minimal`; add `LX_SKIP_MODEL_PREFETCH` flag
```

## PR Description (example)

- Make `dev-minimal` the primary Quickstart path (offline-first).
- Document `LX_SKIP_MODEL_PREFETCH` to disable model prefetch during setup.
- Gate any prefetch script behind the flag.
- CI remains unchanged. Tight diffs; no behavior change for existing users unless they opt into the flag.

**Verification:** See steps in this task. All checks should pass locally in lightweight mode.

---

## Out of Scope (explicitly)

- Dependency pruning/renames (tracked separately in Epic items 4 & 7).
- VS Code tasks consolidation (Epic item 3).
- GPU enablement toggles and profiles.
```
