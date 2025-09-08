# AGENTS.md

This repository uses GitHub Copilot **agent mode**. Roles:
- Product lead: you
- Senior dev: Lex
- Junior dev: Copilot (agent)

The agent should follow these steps exactly when running tasks.

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
echo "No build step"
```

## Test
- Manual checklists live in the task deliverables.
- If tests/ exists, run its suite (e.g., pytest).

## Quality Gates
- Minimal, focused diffs.
- Valid Markdown (closed fences).
- POSIX-friendly shell when possible.

## PR Rules
- Commit style: imperative ("Add...", "Fix...", "Update...").
- No secrets/CI/deploy edits unless explicitly instructed.
- Reference the task file used.

## Task Source of Truth
- Prefer ./.github/copilot/current-task-deliverables.md if present.
- Else use new-task-deliverables.md

## Guardrails
- No destructive commands.
- No deleting out-of-scope files.
- Ask for clarification if acceptance criteria are unclear.
