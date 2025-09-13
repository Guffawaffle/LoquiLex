#instruction
Execute the task described in `.github/copilot/current-task.md` while adhering to all project rules and guidance defined in `AGENTS.md`.

#requirements
- Perform the task exactly as written in `current-task.md`.
- Apply all conventions, constraints, and workflows described in `AGENTS.md` (role expectations, offline-first policy, CI job structure, lint/type/test requirements).
- Provide detailed outputs in a new file: `.github/copilot/current-task-deliverables.md`.
- Do **not** shorten, omit, or over-summarize. Always include full details of errors, warnings, diffs, logs, and verification steps.

#deliverable-format
In `.github/copilot/current-task-deliverables.md`, include:

1. **Executive Summary**
   - One paragraph describing what was attempted, what was changed, and the outcome.

2. **Steps Taken**
   - Bullet points of how the task was approached and executed.
   - Reference any code changes, test runs, or CI updates.

3. **Evidence & Verification**
   - Full command outputs (pytest, mypy, ruff, etc.).
   - Before/after diffs or code snippets.
   - Logs and stack traces where relevant.
   - Do not truncate — include the complete context needed for analysis.

4. **Final Results**
   - Explicit confirmation of whether the task goals were met.
   - Any remaining warnings, skipped items, or follow-up recommendations.

5. **Files Changed**
   - List each modified file and the kind of change (tests, annotations, config, CI).

#output
Write only the deliverables report into `.github/copilot/current-task-deliverables.md`.
