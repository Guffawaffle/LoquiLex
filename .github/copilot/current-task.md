# current-task.md (redirector)

#instruction
Treat the **GitHub issue you are currently assigned** as the task to execute. Use **`.github/copilot/main.prompt.md`** as the single source of truth for how to work. Wherever that prompt references “current-task.md”, substitute the **full body of the assigned issue**.

#requirements
- **Search the repository** for existing functions/classes/utilities before adding new ones. Never assume APIs exist.
- Use the issue’s **Acceptance Criteria** as the test oracle when present.
- Keep diffs minimal and reviewable; prefer adapters/shims over rewrites.
- Produce a **deliverables report** using the format defined in `main.prompt.md` and write it to:
  `.github/copilot/current-task-deliverables.md`.
- Do **not** truncate logs or outputs; include full command output (pytest, mypy/ruff, etc.).

#output
Write **only** the deliverables report to `.github/copilot/current-task-deliverables.md`.
