# Task: PR #43 — Unblock container `make ci` (fix mypy-only blockers)

**Timestamp:** 2025-09-14 10:32 CDT
**Context:** Docker exec issues are resolved. The remaining failure for `make ci` inside the container is **mypy**. We will **only** address type-check errors that block CI (no behavioral changes).

## Intent
Make `make ci` pass **inside the Docker CI image** by fixing/cleaning typing issues: remove unused `# type: ignore` comments, replace invalid `any` annotations with `typing.Any`, add minimal missing annotations, and narrow union types at call sites. Do **not** change runtime semantics.

## Branch
Operate on the PR #43 head branch. If already on a working branch for this effort, continue there. Otherwise:
```bash
gh pr view 43 --json headRefName,url --jq '.headRefName + " ← " + .url'
git fetch origin pull/43/head:pr-43 && git checkout pr-43
git checkout -b fix/43-mypy-ci
```

## Constraints
- **Scope**: Fix only mypy blockers reported by `make ci` inside the container. No feature changes.
- **Offline-first**: Do not add any network/model downloads to tests.
- **Minimal diffs**: Keep edits as small and local as possible.
- **Commit style**: Imperative, focused commits.
- **No repo settings changes**. If something requires UI-only changes, record as **Manual Step Required**.

---

## Baseline (record current state)
Run and capture outputs (for deliverables):
```bash
docker build -t loquilex-ci -f Dockerfile.ci .
docker run --rm -v "$(pwd)":/app -w /app --entrypoint /usr/bin/make loquilex-ci ci
```
Save the full mypy error list (file, line, error code) into the deliverables.

---

## Changes to Apply (surgical)

### 1) Add mypy config for optional deps
Create **`mypy.ini`** at repo root (or merge into existing config). This prevents code-level ignores for third-party stubs:
```ini
[mypy]
python_version = 3.12
warn_unused_ignores = True
warn_redundant_casts = True
warn_unreachable = True
no_implicit_optional = True

[mypy.torch.*]
ignore_missing_imports = True

[mypy.transformers.*]
ignore_missing_imports = True
```
> If `pyproject.toml` already configures mypy, add the equivalent sections there instead of creating `mypy.ini`.

### 2) Replace invalid `any` with `typing.Any` in **`loquilex/asr/metrics.py`**
- `from typing import Any` (add to imports)
- Change function annotations:
  - `get_summary(self) -> Dict[str, Any]`
  - `on_partial_event(self, event: Dict[str, Any]) -> None`
  - `on_final_event(self, event: Dict[str, Any]) -> None`
  - `_safe_get(self, d: Dict[str, Any], key: str, default: Any = None) -> Any`

### 3) Minimal missing annotations
- **`loquilex/asr/stream.py`**:
  - `from typing import List`
  - `words: List[ASRWord] = []` (use the project’s word type alias if different)
- **`loquilex/asr/aggregator.py`**:
  - `from typing import Set`
  - `self.finalized_segment_ids: Set[str] = set()`

### 4) Session typing & narrowing (no behavior change)
- **`loquilex/api/supervisor.py`**
  - `from typing import Optional, Union`
  - Fields:
    - `self.asr: Optional[StreamingASR] = None`
    - `self.aggregator: Optional[PartialFinalAggregator] = None`
    - `self._sessions: Dict[str, Union[Session, StreamingSession]] = {}`
  - Guarded warmup:
    - `if self.asr is not None: self.asr.warmup()`
  - Narrow before calling session-specific methods:
    - `if isinstance(sess, StreamingSession): ... else: raise HTTPException(status_code=400, detail="streaming session required")`

- **`loquilex/api/server.py`**
  - Use `isinstance(sess, StreamingSession)` before calling `get_metrics()` / `get_asr_snapshot()`.
  - For non-streaming sessions: `raise HTTPException(status_code=400, detail="streaming session required")`.

> Do **not** alter success payloads or existing test expectations.

### 5) Remove unused `# type: ignore` comments
- Search in `loquilex/mt/translator.py`, `loquilex/api/supervisor.py`, and any files flagged by `warn_unused_ignores`.
- If an ignore is still necessary, scope it (e.g., `# type: ignore[assignment]`).

### 6) Tidy “unreachable code” patterns (no semantic change)
- **CLI (`loquilex/cli/live_en_to_zh.py`)**:
  ```py
  if __name__ == "__main__":
      raise SystemExit(main())
  ```
- If mypy flags statements after `return`/`raise`, restructure with `if/else`. For impossible branches, Python 3.12’s:
  ```py
  from typing import assert_never
  ...
  else:
      assert_never(sess)
  ```

---

## Re-run & Verify
Execute inside container and record outputs:
```bash
docker build -t loquilex-ci -f Dockerfile.ci .

# Primary gate
docker run --rm -v "$(pwd)":/app -w /app   --entrypoint /usr/bin/make loquilex-ci ci

# Optional: dead-code report using container Python
docker run --rm -v "$(pwd)":/app -w /app   -e VENV_PY=/opt/venv/bin/python   --entrypoint /usr/bin/make loquilex-ci dead-code-analysis
```

## Deliverables → `.github/copilot/current-task-deliverables.md`
1. **Executive Summary**: what changed and outcome.
2. **Steps Taken**: commands and brief rationale.
3. **Evidence & Verification**: full mypy/ruff/pytest outputs from the container; list of files/lines fixed.
4. **Final Results**: pass/fail against acceptance criteria.
5. **Files Changed**: each file with purpose (types/annotations/config only).

## Acceptance Criteria
- `make ci` **passes inside the Docker container** (`loquilex-ci` image), with **zero** mypy errors.
- No runtime behavior changes (tests remain green).
- Changes limited to typing/config and unreachable-code tidying.
- Commits are imperative and minimal; outputs captured in deliverables.
