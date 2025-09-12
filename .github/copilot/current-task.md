#task
Investigate and fix failing tests in the LoquiLex repository.

#context
- Repo: LoquiLex (Python 3.12, FastAPI, WebSockets, Whisper/NLLB offline pipeline).
- CI currently shows failing tests. We need to identify root causes and resolve them without breaking our **local-first / offline** guarantees.

#instructions
- Run the full pytest suite (`pytest -q --maxfail=1 --disable-warnings`).
- Collect failing tests, stack traces, and error messages.
- Diagnose whether each failure is due to:
  1. Incorrect test expectations.
  2. Missing mocks for network/model calls (must be offline-safe).
  3. Code regressions introduced in recent commits.
- Propose minimal diffs to fix tests:
  - Adjust code if behavior is wrong.
  - Adjust test if the assertion is outdated.
  - Add fakes/mocks to replace external calls (no HuggingFace/remote fetches).
- Re-run tests to confirm all pass locally.

#plan
1. Enumerate all failing tests with context.
2. Categorize root cause per test.
3. Suggest targeted code/test changes.
4. Verify CI passes offline (network blocked).
5. Summarize in a PR comment:
   - Failing test names & causes.
   - Fixes applied.
   - Confirmation of green CI.

#constraints
- Must remain fully offline-capable.
- No adding `# noqa` or disabling tests.
- Keep changes minimal and scoped to making tests pass.
- Maintain coding style (Black/Ruff).
- Include/adjust mocks where external network or model calls are made.

#deliverables
- Passing pytest suite (unit + e2e).
- Concise PR diff with test/code fixes.
- PR comment with summary of what was fixed and why.
