#instruction
Run the specified `make` target in the LoquiLex repo and fix failures methodically until the target succeeds.

#parameters
- TARGET: <REPLACE with the exact make target, e.g., `test`, `streaming-tests`, `ci`, `lint`, `typecheck`>
- MAKE_FLAGS (optional): <extra flags, e.g., `-k`, `V=1`>
- ISSUE_REF (optional): <e.g., `#29`>

#environment
- Python: 3.12.3
- Offline-first: export HF_HUB_OFFLINE=1, TRANSFORMERS_OFFLINE=1, HF_HUB_DISABLE_TELEMETRY=1, LOQUILEX_OFFLINE=1
- Use Makefile targets as the source of truth (don’t run tools directly unless the target does so).
- Respect repo rules in `AGENTS.md` (commit style, CI/lint/type/test requirements, minimal diffs).

#process
1. **Dry run**
   - If supported, run: `make -n ${TARGET} ${MAKE_FLAGS}` to preview steps.
   - Then run: `make ${TARGET} ${MAKE_FLAGS}` and capture full stdout/stderr.

2. **Triage the FIRST blocking error**
   - Identify the root cause (not just the symptom).
   - Propose the smallest viable fix (code/tests/config) that aligns with project principles (offline-first, transparency, minimal diffs).
   - Avoid broad refactors; prefer surgical edits. Do not bypass checks (no `-k` to skip tests unless explicitly passed via MAKE_FLAGS).

3. **Apply fix and re-run**
   - Edit files as needed.
   - Re-run `make ${TARGET} ${MAKE_FLAGS}`.
   - Repeat triage → minimal fix → re-run until the target exits 0 or a genuine blocker is reached.

4. **Quality gates**
   - If the target doesn’t run all gates, also run: `make lint`, `make typecheck`, and `make test -k` as appropriate.
   - Ensure `ruff` passes, `mypy` is clean (or strictly improved), and tests pass locally.
   - Keep commit messages **imperative** (e.g., `fix(streaming): …`). Reference ISSUE_REF if provided.

5. **Makefile/CI edits (only if necessary)**
   - If a target is broken by definition, fix the Makefile minimally.
   - If CI config must change, justify the necessity and keep the diff minimal.

#deliverable-format
Write **only** the following report to `.github/copilot/current-task-deliverables.md`:

1. **Executive Summary**
   - What target was run, the main failures found, key changes made, and the outcome.

2. **Steps Taken**
   - Bullet list of each attempt: command(s) run, diagnosis, and edits applied.

3. **Evidence & Verification**
   - Paste full command outputs for failing → passing runs (`make …`, `ruff`, `mypy`, `pytest`).
   - Include before/after diffs or code snippets for all changes.

4. **Final Results**
   - Explicit pass/fail for the target.
   - Residual warnings, TODOs, or follow-ups (if any).

5. **Files Changed**
   - List each modified file with a brief note (tests, implementation, Makefile, CI, docs).

#constraints
- Do not delete tests or disable checks to “make it green.”
- Keep diffs tight and well-justified.
- Maintain offline determinism; no network calls in tests.
- Prefer `anyio`-compatible async patterns in tests.

#output
- Commit changes with imperative messages (e.g., `fix(asr): prevent loop mismatch in thread handoff`).
- Produce `.github/copilot/current-task-deliverables.md` exactly as specified.

#run
- TARGET: <FILL>
- MAKE_FLAGS: <optional>
- ISSUE_REF: <optional>
