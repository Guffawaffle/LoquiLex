---
mode: 'agent'
model: GPT-4.1
tools: ['githubRepo', 'codebase']
description: 'Execute the repo’s current task and record full deliverables (pinned to GPT-4.1).'
---

## Instruction
Execute the task described in `.github/copilot/current-task.md` while adhering to all project rules and guidance defined in `AGENTS.md`.

## Priority
Follow these in strict order of precedence: instruction → requirements → deliverable format → output.

## Requirements
- Perform the task exactly as written in `current-task.md`.
- Apply all conventions, constraints, and workflows described in `AGENTS.md` (role expectations, offline-first policy, CI job structure, lint/type/test requirements).
- Provide detailed outputs in a new file: `.github/copilot/current-task-deliverables.md`.
- Do **not** shorten, omit, or over-summarize. Always include full details of errors, warnings, diffs, logs, and verification steps.
- If a step fails, include the full error output. Stop only if continuing would produce misleading results; otherwise, continue with partial evidence.
- Confirm commit messages follow imperative style and diffs remain minimal.

## Deliverable Format
In `.github/copilot/current-task-deliverables.md`, include the standard sections: Executive Summary, Steps Taken, Evidence & Verification, Final Results, Files Changed.

## Output
Write only the deliverables report into `.github/copilot/current-task-deliverables.md`. No additional commentary outside this file.
