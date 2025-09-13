#instruction
Execute the task described in `.github/copilot/current-task.md` while adhering to all project rules and guidance defined in `AGENTS.md`.

#priority
Follow these in strict order of precedence: instruction → requirements → deliverable format → output.

#requirements
- Perform the task exactly as written in `current-task.md`.
- Use the branch specified in `current-task.md`. Do not work on `main`.
- Apply all conventions, constraints, and workflows described in `AGENTS.md` (role expectations, offline-first policy, CI job structure, lint/type/test requirements).
- If the task requires GitHub UI-only changes (e.g., repository settings), DO NOT attempt to automate them. Instead, note them clearly as **Manual Step Required** with exact click-path.
- Provide detailed outputs in a new file: `.github/copilot/current-task-deliverables.md`.
- Do **not** shorten, omit, or over-summarize. Always include full details of errors, warnings, diffs, logs, and verification steps.
- If a step fails, include the full error output. Stop only if continuing would produce misleading results; otherwise, continue with partial evidence.
- Confirm commit messages follow **imperative** style and diffs remain **minimal** (no unrelated formatting churn).
- Record exact commands executed and link to all relevant GitHub Actions run URLs/IDs.
- Do not expose secrets. Redact tokens/keys and avoid printing environment variables that could contain secrets.

#deliverable-format
In `.github/copilot/current-task-deliverables.md`, include:

1. **Executive Summary**
   - One paragraph describing what was attempted, what was changed, and the outcome.

2. **Steps Taken**
   - Bullet points of how the task was approached and executed.
   - Reference any code changes, test runs, CI updates, and manual steps (if any).

3. **Evidence & Verification**
   - Full command outputs (pytest, mypy, ruff, etc.), with sensitive data redacted.
   - Before/after diffs or code snippets.
   - Links to workflow runs (URLs/IDs), logs, and stack traces where relevant.
   - Record environment details where relevant (Python version, dependency versions, CI job names).

4. **Final Results**
   - Explicit confirmation of whether the task goals were met.
   - Any remaining warnings, skipped items, or follow-up recommendations (and linked issues if created).

5. **Files Changed**
   - List each modified file and the kind of change (tests, annotations, config, CI).

#output
Write only the deliverables report into `.github/copilot/current-task-deliverables.md`. No additional commentary outside this file.
