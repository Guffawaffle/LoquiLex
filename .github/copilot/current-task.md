# Current Task — Stabilize E2E WebSocket Tests & Enforce Offline-First Guards (PR #25 follow-up)

> Branch: `copilot/fix-9` → target `main`
> Scope: Tests, small config hardening, CI env consistency, and minor code nits.
> Goal: Eliminate flakiness and ensure strict offline isolation while keeping tests fast (<1s/test).

---

## Objectives (Do all of these)

1. **Bound WebSocket receive operations with timeouts** in `tests/test_e2e_websocket_api.py` so no hang can occur in CI.
2. **Make network-forbidding explicit** in isolation tests: apply `pytestmark = pytest.mark.usefixtures("forbid_network")` (or equivalent) so tests never hit the real network even if autouse drifts.
3. **Harden offline env expectations** across test runners:
   - Ensure `HF_HUB_OFFLINE=1`, `TRANSFORMERS_OFFLINE=1`, `HF_HUB_DISABLE_TELEMETRY=1`, `LOQUILEX_OFFLINE=1` are consistently set in CI and local `make test`.
   - In tests, fail with a clear message **or** skip with rationale when envs are intentionally absent (configurable via mark).
4. **Enforce LX-only env policy**: remove or strictly guard any generic `_env()` helper introduced in `loquilex/config/defaults.py` (allow only `LX_*` names to prevent backsliding to legacy prefixes).
5. **Stabilize host allowances** in offline tests: only allow `127.0.0.1` and `localhost`. Do **not** rely on `testserver` DNS behavior.
6. **Keep tests crisp**: move inline imports to module top, align docstring timing claims with asserted thresholds, and add minimal logging for clarity where helpful.
7. **Pass CI** with green `ruff`, `mypy`, and `pytest` under offline constraints; all tests must complete < 90s total on CI runners.

---

## Acceptance Criteria

- ✅ `pytest -q` passes locally and in CI with **no external network** access.
- ✅ No test blocks longer than the specified timeout; WebSocket test completes under **1.0s** wall time (with an internal target ≈0.5–0.7s).
- ✅ `ruff check .` reports **0** errors/warnings.
- ✅ `mypy` passes at the repo’s configured strictness (no regressions).
- ✅ `.github/copilot/current-task-deliverables.md` contains full logs and evidence (see Deliverables section).

---

## Implementation Plan

### A) WebSocket test: bounded receive
- Replace any raw `ws.receive()` calls with a bounded wait. Two acceptable approaches:

**Option 1 (anyio):**
```python
import anyio

with anyio.fail_after(0.8):  # hard cap (seconds)
    msg = ws.receive()
```

**Option 2 (thread wrapper):**
```python
import queue, threading

q: "queue.Queue[object]" = queue.Queue()

def _recv():
    try:
        q.put(ws.receive())
    except Exception as e:
        q.put(e)

t = threading.Thread(target=_recv, daemon=True)
t.start()
t.join(timeout=0.8)
assert not t.is_alive(), "WebSocket receive hung >0.8s"
obj = q.get_nowait()
if isinstance(obj, Exception):
    raise obj
msg = obj
```

- Keep a **safety assertion** (`<=1.0s`) around the whole connect→ping→recv→close sequence.
- Align comments/docstrings with the actual thresholds (don’t say “≤500ms” if asserting 1.0s).

### B) Explicit offline guard in tests
At the top of `tests/test_offline_isolation.py`:
```python
import pytest
pytestmark = pytest.mark.usefixtures("forbid_network")
```

- If a `forbid_network` fixture does **not** exist yet, add one centrally (e.g., `tests/conftest.py`) that blocks non-loopback sockets (monkeypatch `socket.create_connection`, `socket.socket.connect`). Allow only `('127.0.0.1', *)` and `('::1', *)`.
- The fixture must be **idempotent** and fast.

### C) Offline env expectations
- Ensure these are exported in CI and local commands:
  - `HF_HUB_OFFLINE=1`
  - `TRANSFORMERS_OFFLINE=1`
  - `HF_HUB_DISABLE_TELEMETRY=1`
  - `LOQUILEX_OFFLINE=1`
- Update `Makefile` test target to export them for local runs.
- In a dedicated test (`tests/test_offline_env.py`), assert they are set **or** skip with a clear reason if a mark `@pytest.mark.allow_missing_offline_envs` is present. Default behavior should be **strict** (fail) to catch drift in CI.

### D) Enforce LX-only env policy
- Remove or harden any new `_env()` helper in `loquilex/config/defaults.py`:
  - If kept, implement:
    ```python
    def _env(name: str, default: str | None = None) -> str | None:
        if not name.startswith("LX_"):
            raise ValueError(f"Only LX_* env vars are allowed, got: {name}")
        return os.getenv(name, default)
    ```
  - Prefer direct, explicit `os.getenv("LX_FOO")` in app code to reduce indirection.
- Audit for prohibited legacy fallbacks (GF_*) — none should remain.

### E) Host allowlist in tests
- In the offline tests, only use `localhost` and `127.0.0.1` (and FastAPI’s in-proc `TestClient`). Remove `testserver` references.

### F) Small QoL/Nits
- Move any inline imports (`time`, etc.) to module top.
- Add one-line info logs where it helps triage (e.g., resolved model path when `LX_SKIP_MODEL_PREFETCH=1`).

---

## Patch Sketches (apply/adapt to actual file names)

> **Note:** Treat these as templates; adjust line numbers as needed.

**1) tests/test_e2e_websocket_api.py**
```diff
@@
-    # receive without an explicit bound
-    msg = ws.receive()
+    # Bounded receive to avoid CI hangs
+    with anyio.fail_after(0.8):
+        msg = ws.receive()
@@
-    # comment says ≤500ms but we assert <=1.0s later
-    assert elapsed <= 1.0
+    # Target ~0.5–0.7s; hard cap 1.0s for safety
+    assert elapsed <= 1.0
```

**2) tests/test_offline_isolation.py**
```diff
+import pytest
+pytestmark = pytest.mark.usefixtures("forbid_network")
@@
-    allowed = {"localhost", "127.0.0.1", "testserver"}
+    allowed = {"localhost", "127.0.0.1"}
```

**3) tests/conftest.py** (only if fixture missing or to standardize behavior)
```diff
+import os, socket
+import pytest
+from contextlib import contextmanager
+
+@pytest.fixture(scope="session")
+def forbid_network(monkeypatch):
+    real_create_connection = socket.create_connection
+    def guarded(addr, *args, **kwargs):
+        host, *_ = addr
+        if host not in {"127.0.0.1", "::1", "localhost"}:
+            raise RuntimeError(f"External network blocked: {addr}")
+        return real_create_connection(addr, *args, **kwargs)
+    monkeypatch.setattr(socket, "create_connection", guarded, raising=True)
```

**4) loquilex/config/defaults.py** (enforce LX-only)
```diff
@@
-def _env(name: str, default: str | None = None) -> str | None:
-    return os.getenv(name, default)
+def _env(name: str, default: str | None = None) -> str | None:
+    if not name.startswith("LX_"):
+        raise ValueError(f"Only LX_* env vars are allowed, got: {name}")
+    return os.getenv(name, default)
```

**5) scripts/dev_fetch_models.py** (QoL echo)
```diff
@@
 if os.getenv("LX_SKIP_MODEL_PREFETCH") == "1":
-    sys.exit(0)
+    print("[dev_fetch_models] Skipping model prefetch due to LX_SKIP_MODEL_PREFETCH=1")
+    sys.exit(0)
```

**6) Makefile** (ensure offline envs in test target)
```diff
 test:
-	pytest -q
+	HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 HF_HUB_DISABLE_TELEMETRY=1 LOQUILEX_OFFLINE=1 pytest -q
```

---

## Commands to Run (local & CI parity)

```bash
# From repo root
make fmt-check
make lint        # ruff
make type        # mypy
make test        # ensures offline envs are set
```

If individual test debugging is needed:
```bash
HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 HF_HUB_DISABLE_TELEMETRY=1 LOQUILEX_OFFLINE=1 \
pytest -vv tests/test_e2e_websocket_api.py::test_websocket_roundtrip
```

---

## Deliverables (write all of this to `.github/copilot/current-task-deliverables.md`)

1. **Executive Summary** — what changed and why.
2. **Steps Taken** — bullets with file edits and decisions.
3. **Evidence & Verification** — include full outputs (no truncation):
   - `ruff check .`
   - `mypy`
   - `pytest -vv` (show timing for WebSocket test)
4. **Final Results** — did we meet all acceptance criteria?
5. **Files Changed** — list each file and the type of change.

> Include any failure logs encountered along the way and how they were resolved.

---

## Notes / Constraints

- Prefer **no new runtime deps** in app code. `anyio` is already present via `httpx`/`starlette` (if available); otherwise use the thread wrapper.
- Keep tests self-contained and fast. No sleeps > 50ms unless strictly necessary.
- Do not touch deploy/secrets workflows in this task.
