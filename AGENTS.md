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
- **Commit style**: imperative mood (`Add…`, `Fix…`, `Update…`).
- **PR description**: must include WHAT changed and WHY, and reference the task issue.
- **No secrets/CI/deploy edits** unless explicitly instructed.
- **Task Source of Truth**:
  - If `.github/copilot/current-task-deliverables.md` exists → follow it.
  - Otherwise, follow acceptance criteria from the assigned issue.

---

## Guardrails
- Never run destructive commands.
- Never delete or edit out-of-scope files.
- If acceptance criteria are unclear, **open a question in the PR** instead of guessing.
- Follow repo conventions (tests required, semantic commits, docs when behavior changes).
