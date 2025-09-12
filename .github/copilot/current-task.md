#task
Fix remaining mypy type errors in LoquiLex repository, focusing on three modules: `audio/capture.py`, `cli/live_en_to_zh.py`, and `api/server.py`.

#context
- Repo: LoquiLex (Python 3.12, FastAPI, WebSockets, Whisper/NLLB offline pipeline).
- Mypy has already been integrated in warn-only mode, with `model_discovery.py` type issues resolved.
- Current status: 4 errors remain across 3 files (`audio/capture.py`, `cli/live_en_to_zh.py`, `api/server.py`).

#instructions
1. Run mypy on the entire repo to confirm exact errors:
   ```bash
   mypy loquilex
   ```
2. For each failing file:
   - Identify the exact lines and error messages.
   - Add or refine type hints (`Callable`, `List`, `Dict[str, Any]`, `Optional`, etc.).
   - Use `from typing import Any` when necessary, but prefer precise types where feasible.
   - Refactor logic if a type mismatch is genuine (e.g., string vs. int).
3. Ensure all fixes maintain **offline-first** behavior (no new deps, no network code).
4. Re-run mypy to confirm those modules pass with **0 errors**.
5. Leave other modules as-is (they may still have warnings, but focus only on these 3 files for now).
6. Update docstrings and function signatures to reflect new type hints.

#plan
- Investigate mypy output for the 3 target files.
- Apply type fixes iteratively, preferring precise annotations.
- Use `typing.Any` only as a last resort.
- Verify fixes by re-running mypy locally on just the target modules and then the entire repo.

#constraints
- Do not silence errors with `# type: ignore` unless absolutely unavoidable.
- Do not add new dependencies beyond `typing` or `collections.abc` imports.
- Keep changes minimal but correct, no major rewrites.

#deliverables
- Clean `mypy` run for:
  - `loquilex/audio/capture.py`
  - `loquilex/cli/live_en_to_zh.py`
  - `loquilex/api/server.py`
- Updated function/type annotations in those modules.
- A PR commit with message:
  `fix(types): resolve mypy errors in capture, live CLI, and server modules`
