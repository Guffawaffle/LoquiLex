---
mode: 'agent'
model: GPT-4o
tools: ['githubRepo', 'codebase']
description: 'Finalize: verify success and rotate the current task safely.'
---

## Instruction
If the current task is complete and tests are green, rotate the task using the repository script and log the rotation output.

## Steps
1. Verify that `.github/copilot/current-task-deliverables.md` exists and confirms success.
2. In a VS Code terminal, run:
   ```bash
   bash .github/copilot/rotate-task.sh
   ```
3. Capture the full stdout/stderr of the rotation command.
4. Append a new section to `.github/copilot/current-task-deliverables.md` named **Task Rotation Log**, containing:
   - The exact command run.
   - The full command output.
   - Any new/renamed files created by the rotation.
5. If verification in Step 1 indicates the task is not complete or tests are not green, do **not** rotate. Instead, append a short note under **Task Rotation Log** explaining why rotation was skipped.

## Output
Only modify `.github/copilot/current-task-deliverables.md` by appending the **Task Rotation Log** section. Do not create other files or comments.
