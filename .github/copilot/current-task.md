# Current Task — PR #25 Hardening: Bound WS recv, explicit offline guard, env consistency, and small cleanups

> Branch: `copilot/fix-9` (PR #25) → target `main`
> Scope: Tests (`tests/test_e2e_websocket_api.py`, `tests/test_offline_isolation.py`, `tests/conftest.py`), config (`loquilex/config/defaults.py`), Makefile.
> Goal: Eliminate WS hang risk, make network guard explicit/reliable, ensure offline envs, and enforce LX-only env policy.

## Objectives (Do all)

1. **Bound WebSocket receive** with a hard timeout; keep total WS round-trip ≤1.0s.
2. **Explicit `forbid_network` fixture** and apply via `pytestmark` in offline tests.
3. **Remove `testserver`** from allowlist; only loopback hosts.
4. **Make offline envs consistent**: `make test` exports the offline envs; tests remain strict.
5. **Enforce LX-only env policy**: restrict or remove `_env()` helper.
6. **Nits/QoL**: move inline imports to top; clarify timing comments; tiny echo in `dev_fetch_models.py` when skipping.

## Patch Sketches (apply/adapt)

### 1) `tests/test_e2e_websocket_api.py` — bounded receive

```diff
@@
-    # Short recv with timeout to ensure we don't hang waiting for frames
-    # This fulfills the requirement: connect → ping → short recv (≤500ms) → close
-    import time
-    start_time = time.time()
-    try:
-        # Try to receive any message - this should timeout quickly
-        # FastAPI TestClient WebSocket uses receive() instead of receive_text()
-        ws.receive()
-        recv_time = time.time() - start_time
-        # If we got a response, verify it came quickly (within 500ms as required)
-        assert recv_time <= 0.5, f"Response took too long: {recv_time}s"
-    except Exception:
-        # Timeout or connection error is expected in test environment
-        recv_time = time.time() - start_time
-    # Ensure we didn't hang - should complete within reasonable time
-    assert (
-        recv_time <= 1.0
-    ), f"recv() took too long to timeout: {recv_time}s"
+    # Bounded recv to eliminate any chance of hanging the test
+    import time, queue, threading
+    start_time = time.time()
+    q: "queue.Queue[object]" = queue.Queue()
+
+    def _recv():
+        try:
+            q.put(ws.receive())
+        except Exception as e:
+            q.put(e)
+
+    t = threading.Thread(target=_recv, daemon=True)
+    t.start()
+    t.join(timeout=0.8)  # hard cap
+    elapsed = time.time() - start_time
+    assert not t.is_alive(), f"WebSocket receive hung >0.8s (elapsed={elapsed:.3f}s)"
+    obj = q.get_nowait()
+    if isinstance(obj, Exception):
+        # In our lightweight test, an exception/timeout is acceptable
+        pass
+    # Target ~0.5–0.7s; hard cap 1.0s for safety
+    assert elapsed <= 1.0, f"WS roundtrip exceeded 1.0s (elapsed={elapsed:.3f}s)"
```

> If `anyio` is available, using `anyio.fail_after(0.8)` is also acceptable.

### 2) `tests/test_offline_isolation.py` — explicit guard & host allowlist

```diff
@@
-"""Test network isolation and offline behavior in tests."""
+"""Test network isolation and offline behavior in tests."""
+import pytest
+pytestmark = pytest.mark.usefixtures("forbid_network")
@@
-allowed_hosts = ["127.0.0.1", "localhost", "testserver"]
+allowed_hosts = ["127.0.0.1", "::1", "localhost"]
```

### 3) `tests/conftest.py` — add `forbid_network` fixture (if not present)

```diff
+import socket
+import pytest
+
+@pytest.fixture(scope="session")
+def forbid_network(monkeypatch):
+    real_create_connection = socket.create_connection
+
+    def guarded(address, *args, **kwargs):
+        host = address[0] if isinstance(address, tuple) else address
+        if host not in {"127.0.0.1", "::1", "localhost"}:
+            raise RuntimeError(f"Blocked outbound connection to {host}")
+        return real_create_connection(address, *args, **kwargs)
+
+    monkeypatch.setattr(socket, "create_connection", guarded, raising=True)
```

### 4) `Makefile` — ensure offline envs in `test` target

```diff
-test:
-	pytest -q
+test:
+	HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 HF_HUB_DISABLE_TELEMETRY=1 LOQUILEX_OFFLINE=1 pytest -q
```

### 5) `loquilex/config/defaults.py` — enforce `LX_*` only

```diff
-def _env(name: str, default: str) -> str:
-    return os.getenv(name, default)
+def _env(name: str, default: str) -> str:
+    if not name.startswith("LX_"):
+        raise ValueError(f"Only LX_* env vars are allowed, got: {name}")
+    return os.getenv(name, default)
```

### 6) `scripts/dev_fetch_models.py` — tiny echo when skipping

```diff
-if is_truthy(os.getenv("LX_SKIP_MODEL_PREFETCH")):
-    print("[dev] LX_SKIP_MODEL_PREFETCH set — skipping model prefetch.")
-    sys.exit(0)
+if is_truthy(os.getenv("LX_SKIP_MODEL_PREFETCH")):
+    print("[dev] Skipping model prefetch due to LX_SKIP_MODEL_PREFETCH=1")
+    sys.exit(0)
```

## Commands

```bash
make fmt-check && make lint && make type && make test
pytest -vv tests/test_e2e_websocket_api.py::test_e2e_websocket_live_session
pytest -vv tests/test_offline_isolation.py
```

## Acceptance Criteria

- Pytests green; WS test ≤1.0s; no external network; ruff/mypy clean; `_env()` restricted.

## Deliverables

- Update `.github/copilot/current-task-deliverables.md` with summary, steps, logs, results, files changed.
