# AGENTS.md

This repository uses GitHub Copilot **Coding Agent** (Preview).
Roles:
- **Product lead:** you (maintainer/reviewer)
- **Senior dev:** Lex (advisor/context)
- **Junior dev:** Copilot (agent)

The agent must follow these steps when working on tasks.

---

## Setup
```bash
python3 -m venv .venv
. .venv/bin/activate
[ -f requirements.txt ] && pip install -r requirements.txt
[ -f package.json ] && npm ci
[ -f composer.json ] && composer install --no-interaction
```

## Build
```bash
# If no build step is required, skip.
echo "No build step"
```

## Test
- If `tests/` exists, run its suite (e.g., `pytest`, `npm test`, etc.).
- Ensure all lint/type-check targets in CI pass (`ruff`, `mypy`, `phpcs`, etc. if defined).
- Manual checklists or extra validation should be included in **task deliverables**.

---

## Quality Gates
- **Minimal, focused diffs**: only touch files in scope.
- **Valid Markdown** (no broken fences).
- **POSIX-friendly shell** where scripts are required.
- **CI green**: All tests, lint, and type checks must pass before PR is ready.

---

## PR Rules
- **Commit style**: Use imperative mood (`Add…`, `Fix…`, `Update…`).
- **PR description**: Must include WHAT changed, WHY it changed, and reference the related task issue.
- **No secrets/CI/deploy edits** unless explicitly instructed.

- **Task Source of Truth**
  - If `.github/copilot/current-task.md` exists, treat it as the authoritative task description.
  - Otherwise, follow the acceptance criteria in the assigned issue.

- **Task Results**
  - Record a detailed review and output in `.github/copilot/current-task-deliverables.md`.

---

## Deliverables Policy

- After executing a task, always produce `.github/copilot/current-task-deliverables.md` as a detailed running log for the PR.
- Never omit or over-summarize: include full logs, diffs, error messages, and verification steps.

### Deliverables Report Format

Each deliverables file must include:

1. **Executive Summary**
   Concise overview of what was attempted, what changed, and the outcome.

2. **Steps Taken**
   Bullet-point log of how the task was executed (commands, diffs, edits, config changes).

3. **Evidence & Verification**
   - Full command outputs (`pytest`, `mypy`, `ruff`, etc.).
   - Before/after diffs or code snippets.
   - Logs and stack traces where relevant.
   - Do not truncate — include the complete context needed for analysis.

4. **Final Results**
   Whether the goals were met, remaining issues, and follow-up recommendations.

5. **Files Changed**
   List all modified files and the type of change.

### Logging Policy

- `.github/copilot/current-task-deliverables.md` acts as the **running log** for the PR.
- Overwrite or extend this file as needed, but never remove historical context unless instructed.
- This file is part of the review record — keep it detailed and unabridged.

---

## Guardrails
- Never run destructive commands.
- Never delete or edit out-of-scope files.
- If acceptance criteria are unclear, **open a question in the PR** instead of guessing.
- Follow repo conventions (tests required, semantic commits, docs when behavior changes).
