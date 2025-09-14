
# Task: PR #43 Review Fixes — Streaming ASR status, error hygiene, async bridge, cleanup, tests

## Summary
Address review items for PR #43 (Streaming ASR) to ensure correctness, security hygiene, and CI parity. This task corrects snapshot status for thread‑based streaming, removes exception text from HTTP 500 responses, strengthens the thread→async handoff, guarantees audio capture cleanup, and adds targeted tests. Keep diffs minimal and offline‑first.

## Branch
Use the **PR #43 head branch**. If unknown, resolve and work on a short‑lived branch off it:
```bash
gh pr view 43 --json headRefName,url --jq '.headRefName + " ← " + .url'
git fetch origin pull/43/head:pr-43 && git checkout pr-43
git checkout -b fix/43-review
```

## Scope & Constraints
- **Offline-first**: tests must not download models or hit the network—use/extend fakes.
- **No CI/secrets/settings edits** unless required by this task.
- Commit messages **imperative**; diffs **minimal** and PR-scoped.
- Preserve existing event schemas and public interfaces unless noted below.

---

## Tasks

### 1) Correct snapshot status for streaming sessions
`/sessions/{sid}/snapshot` currently derives status from `proc.poll()`. For thread‑based `StreamingSession` there is no `proc`, so status may be incorrect. Detect streaming sessions and compute status from the audio thread.

**Change (illustrative):**
```diff
- running = bool(sess.proc and sess.proc.poll() is None)
+ if isinstance(sess, StreamingSession):
+     th = getattr(sess, "_audio_thread", None)
+     running = bool(th and th.is_alive())
+ else:
+     running = bool(sess.proc and getattr(sess.proc, "poll", lambda: None)() is None)
```

### 2) Sanitize HTTP 500 error bodies
Avoid returning raw exception text in API responses. Log exceptions; return generic details.

**Pattern:**
```diff
- except Exception as e:
-     logger.error(f"metrics error: {e}")
-     raise HTTPException(status_code=500, detail=f"metrics error: {e}")
+ except Exception:
+     logger.exception("metrics error")
+     raise HTTPException(status_code=500, detail="metrics error")
```
Apply similarly to snapshot route and any new endpoints introduced by PR #43.

### 3) Harden thread → asyncio bridge
Store an event loop reference on session start and use `asyncio.run_coroutine_threadsafe` from worker threads. Fall back to a thread‑safe queue if no loop is available yet.

**Illustrative changes:**
```diff
@@ class StreamingSession:
- self.loop = asyncio.get_running_loop()
+ try:
+     self.loop = asyncio.get_running_loop()
+ except RuntimeError:
+     self.loop = None  # set later in async context

@@ in audio worker (thread context):
- asyncio.get_running_loop().create_task(self.broker.publish(evt))
+ if self.loop is not None:
+     asyncio.run_coroutine_threadsafe(self.broker.publish(evt), self.loop)
+ else:
+     # optional: enqueue for later drain on loop
+     self._pending.put(evt)  # if such a queue exists
```

### 4) Guarantee audio capture cleanup
Ensure the audio device is always released—even on early exceptions.

**Pattern:**
```diff
- stop_capture = audio.capture.capture_stream(cfg, on_chunk)
- # ... processing ...
- stop_capture()
+ stop_capture = None
+ try:
+     stop_capture = audio.capture.capture_stream(cfg, on_chunk)
+     # ... processing ...
+ finally:
+     if stop_capture:
+         try:
+             stop_capture()
+         except Exception:
+             logger.exception("stop_capture failed")
```

### 5) Tests (targeted, offline, fast)

**A. Snapshot status correctness**
- Create a streaming session; assert `/sessions/{sid}/snapshot` shows `status == "running"` while the audio thread is alive, then `stopped` after stop.

**B. Error hygiene**
- Force an internal error in metrics/snapshot via monkeypatch and assert `HTTP 500` with `detail == "metrics error"` (no exception text leaked).

**C. Async bridge sanity**
- Unit‑test that from a worker context we call `asyncio.run_coroutine_threadsafe` with the stored loop (patch it and assert call). If a pending queue exists for fallback, assert events are enqueued when `loop is None`.

> Keep using existing fakes; do **not** download models.

### 6) Lint, dead code, and CI parity
```bash
ruff check .
python -m mypy
pytest -q
make dead-code-analysis  # ensure empty vulture report and no F401
```
Optional local CI parity with the docker CI image:
```bash
docker build -t loquilex-ci -f ci/Dockerfile .
docker run --rm -v "$(pwd)":/app -w /app loquilex-ci make run-ci-mode
docker run --rm -v "$(pwd)":/app -w /app loquilex-ci make dead-code-analysis
```

### 7) Commit & push
```bash
git add -A
git commit -m "fix(api): correct snapshot status; sanitize 500s; harden thread→async bridge; ensure capture cleanup; add tests"
git push -u origin HEAD
```

---

## Acceptance Criteria
- Snapshot endpoint returns `running` when the streaming thread is alive, `stopped` after stopping.
- No raw exception text in any 500 responses from metrics/snapshot.
- Worker→loop handoff uses `run_coroutine_threadsafe` (or equivalent); no crashes when no running loop is present.
- Audio capture always cleaned up (no leaked device handles).
- `pytest -q`, `ruff check .`, `mypy`, and `make dead-code-analysis` pass locally and in CI.
- Tests remain offline and fast.

## Deliverables
Write a single report to `.github/copilot/current-task-deliverables.md` including:
1. **Executive Summary**
2. **Steps Taken**
3. **Evidence & Verification** (full outputs, logs, links to GH Actions runs/IDs, environment details)
4. **Final Results**
5. **Files Changed** (with purpose)
