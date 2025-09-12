# Task Deliverables: Fix Remaining MyPy Type Errors

## Executive Summary

Successfully resolved all 4 remaining mypy type errors across 3 modules in the LoquiLex repository: `audio/capture.py`, `cli/live_en_to_zh.py`, and `api/server.py`. All fixes maintain the offline-first behavior and use precise type annotations rather than suppressing errors with `# type: ignore`. The repository now passes mypy type checking with 0 errors across all 22 source files.

## Steps Taken

1. **Initial Error Assessment**
   - Ran `mypy loquilex` to identify the exact 4 type errors in target files
   - Located specific line numbers and error messages for targeted fixing

2. **Fixed audio/capture.py (Line 130)**
   - Added type assertion `assert proc.stdout is not None` in the `reader()` nested function
   - Issue: mypy couldn't narrow the type of `proc.stdout` from `IO[bytes] | None` to `IO[bytes]` after null check
   - Solution: Explicit assertion to inform mypy that stdout is guaranteed to be non-None at that point

3. **Fixed cli/live_en_to_zh.py (Line 233)**
   - Moved `mt_dropped = 0` variable declaration before nested function definitions
   - Removed duplicate declaration that appeared later in the same function
   - Issue: `nonlocal mt_dropped` reference in `on_final()` function couldn't find the binding
   - Solution: Reorganized variable scope by moving declaration to proper location before nested functions

4. **Fixed api/server.py (Lines 228 and 251)**
   - Added `Callable` import to typing imports
   - Changed `stop_fn = None` to `stop_fn: Optional[Callable[[], None]] = None` for proper type annotation
   - Changed `if stop_fn:` to `if stop_fn is not None:` to satisfy mypy's function-in-boolean-context check
   - Fixed string assignment by restructuring `req.asr_model_id or os.getenv("GF_ASR_MODEL") or "small.en"`
   - Issues: Incompatible type assignment and function-always-true-in-boolean-context

5. **Verification Testing**
   - Tested each file individually with mypy after fixes
   - Ran mypy on all 3 target files together
   - Ran full repository mypy check to ensure no regressions

## Evidence & Verification

### Initial MyPy Run (Identifying Errors)
```bash
cd /home/guff/LoquiLex && source .venv/bin/activate && mypy loquilex
```
**Output:**
```
loquilex/audio/capture.py:130: error: Item "None" of "IO[bytes] | None" has no attribute "read"  [union-attr]
loquilex/cli/live_en_to_zh.py:233: error: No binding for nonlocal "mt_dropped" found  [misc]
loquilex/cli/live_en_to_zh.py:421: note: By default the bodies of untyped functions are not checked, consider using --check-untyped-defs  [annotation-unchecked]
loquilex/api/server.py:228: error: Incompatible types in assignment (expression has type "str | None", target has type "str")  [assignment]
loquilex/api/server.py:251: error: Function "stop_fn" could always be true in boolean context  [truthy-function]
Found 4 errors in 3 files (checked 22 source files)
```

### Individual File Verification After Fixes

**audio/capture.py:**
```bash
cd /home/guff/LoquiLex && source .venv/bin/activate && mypy loquilex/audio/capture.py
```
**Output:**
```
Success: no issues found in 1 source file
```

**cli/live_en_to_zh.py:**
```bash
cd /home/guff/LoquiLex && source .venv/bin/activate && mypy loquilex/cli/live_en_to_zh.py
```
**Output:**
```
loquilex/cli/live_en_to_zh.py:421: note: By default the bodies of untyped functions are not checked, consider using --check-untyped-defs  [annotation-unchecked]
Success: no issues found in 1 source file
```

**api/server.py:**
```bash
cd /home/guff/LoquiLex && source .venv/bin/activate && mypy loquilex/api/server.py
```
**Output:**
```
Success: no issues found in 1 source file
```

### Target Files Combined Verification
```bash
cd /home/guff/LoquiLex && source .venv/bin/activate && mypy loquilex/audio/capture.py loquilex/cli/live_en_to_zh.py loquilex/api/server.py
```
**Output:**
```
loquilex/cli/live_en_to_zh.py:421: note: By default the bodies of untyped functions are not checked, consider using --check-untyped-defs  [annotation-unchecked]
Success: no issues found in 3 source files
```

### Full Repository Verification
```bash
cd /home/guff/LoquiLex && source .venv/bin/activate && mypy loquilex
```
**Output:**
```
loquilex/cli/live_en_to_zh.py:421: note: By default the bodies of untyped functions are not checked, consider using --check-untyped-defs  [annotation-unchecked]
Success: no issues found in 22 source files
```

### Code Changes Made

**File: loquilex/audio/capture.py**
```diff
         def reader() -> None:
             bufsize = FRAME_SAMPLES * 4  # float32 bytes
             while not stop_flag.is_set():
+                assert proc.stdout is not None  # Already checked above
                 chunk = proc.stdout.read(bufsize)
                 if not chunk:
                     break
```

**File: loquilex/cli/live_en_to_zh.py**
```diff
     session_t0_mono = None  # will set once first audio frame arrives (monotonic)
     last_t1_mono = None  # monotonic time of latest captured audio end
     audio_since_reset = 0.0  # seconds fed to engine since its last reset
+    mt_dropped = 0  # Count of dropped translation requests due to backlog

     def on_partial(txt: str) -> None:
```

```diff
     # Proper capture loop; start capture and set start time on first frame
     frames: List[np.ndarray] = []
-    mt_dropped = 0

     # Optional audio recording sinks
```

**File: loquilex/api/server.py**
```diff
-from typing import Any, Dict, List, Optional
+from typing import Any, Callable, Dict, List, Optional
```

```diff
     ema = EmaVu(0.4)
     levels: list[float] = []
-    stop_fn = None
+    stop_fn: Optional[Callable[[], None]] = None
```

```diff
-        os.environ["GF_ASR_MODEL"] = req.asr_model_id or os.getenv("GF_ASR_MODEL", "small.en")
+        os.environ["GF_ASR_MODEL"] = req.asr_model_id or os.getenv("GF_ASR_MODEL") or "small.en"
```

```diff
     finally:
-        if stop_fn:
+        if stop_fn is not None:
             try:
                 stop_fn()
```

## Final Results

**✅ SUCCESS:** All task goals were met successfully.

- **4 mypy type errors** resolved across the 3 target files
- **0 type errors** remain in the entire repository (22 source files checked)
- **No new dependencies** added - only used existing `typing` imports
- **Offline-first behavior** maintained - no network code or external dependencies introduced
- **Precise type annotations** used instead of `# type: ignore` suppressions
- **Code quality** maintained with minimal, surgical changes

The remaining note about untyped function bodies in `cli/live_en_to_zh.py:421` is informational only and not an error. This relates to the `--check-untyped-defs` mypy flag and does not prevent successful type checking.

**No remaining warnings, issues, or follow-up actions required** for the specified task deliverables.

## Files Changed

1. **loquilex/audio/capture.py** - Added type assertion for subprocess stdout null check
2. **loquilex/cli/live_en_to_zh.py** - Reorganized variable scope to fix nonlocal binding
3. **loquilex/api/server.py** - Added proper type annotations and improved null checking patterns

**Total files modified:** 3
**Type of changes:** Type annotations, variable scope fixes, import additions
**Lines changed:** ~8 lines across all files
