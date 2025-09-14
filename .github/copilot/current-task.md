# Current Task — PR #27 Polish: docs accuracy, tiny test nit, and CI trigger hygiene

> Branch: `chore/base-camp` (PR #27) → target `main`
> Goal: Merge-ready with precise docs and zero paper cuts.

---

## Objectives (ranked)

### Blocking
1) **Fix duplicate import in `tests/test_compat_versions.py`**
   Remove the stray `import httpx` when `import httpx, starlette, pytest` is present.

2) **Correct docs that reference non-existent files**
   In `.github/copilot/README.md`, either remove or add the referenced `rotate-task.sh` and `main.prompt.md` if they don't exist. Prefer removing refs for now to keep docs truthful.

### Priority
3) **Versioning doc accuracy**
   Copilot README says: “Update version in `pyproject.toml`.” If the repo doesn’t have `pyproject.toml`, change to: “Update version in the project’s version source of truth (e.g., `loquilex/__init__.py`).” Keep references consistent across README and Copilot README.

4) **CodeQL trigger clarity**
   `on.push.branches: ['**']` is valid (all branches, including slashes). Alternatively, omit the filter to mean “all branches.” Choose one approach and keep it consistent across workflows. Ensure there are no empty `schedule:` stanzas.

### QoL
5) **`constraints.txt` commentary**
   Keep the Path A (Keep Pin) rationale in comments and ensure the compatibility set is coherent. Clarify these pins are for **dev/CI determinism**, and that upgrades follow Path B (Coordinated Upgrade) when we choose to bump.

---

## Patch Sketches

### `tests/test_compat_versions.py` — dedupe import

```diff
-from packaging.version import Version
-import httpx
-import starlette
-import httpx, starlette, pytest
+from packaging.version import Version
+import httpx, starlette, pytest
```

### `.github/copilot/README.md` — remove non-existent tool refs (until added)

```diff
- - `main.prompt.md` - **Agent instructions** (workflow rules)
- - `rotate-task.sh` - **Task management script**
+ <!-- If/when these files are added, re-introduce them here. -->
```

### Copilot README — version source of truth

```diff
-1. **Version Bump**: Update version in `pyproject.toml`
+1. **Version Bump**: Update version in the project’s version source of truth (e.g., `loquilex/__init__.py`),
+   and keep README + CHANGELOG in sync.
```

### `.github/workflows/codeql.yml` — triggers (pick one style and stick to it)

**Option A (explicit all branches):**

```yaml
on:
  push:
    branches: ['**']
  pull_request:
    branches: [main]
  # schedule:
  #   - cron: '0 3 * * 1'  # (optional) weekly run
```

**Option B (implicit all branches by omitting filter):**

```yaml
on:
  push:
  pull_request:
    branches: [main]
```

### `constraints.txt` — comment the policy (example snippet)

```text
# Path A (Keep Pin): deterministic dev/CI. Bump via Path B (Coordinated Upgrade)
# when FastAPI/Starlette/httpx are upgraded together after local + E2E validation.
```

---

## Acceptance Criteria

- ✅ Duplicate import removed; tests still pass.
- ✅ Copilot README doesn’t reference missing files; version bump instructions match repo reality.
- ✅ CodeQL workflow triggers are valid YAML and intentional (no empty schedule). `actionlint` is clean.
- ✅ `constraints.txt` clearly states the chosen pinning policy.

## Commands

```bash
make fmt && make fmt-check
make lint && make type && make test
actionlint .github/workflows/codeql.yml
```

## Deliverables

- Update `.github/copilot/current-task-deliverables.md` with a brief summary, the diffs, and a post-merge note.
