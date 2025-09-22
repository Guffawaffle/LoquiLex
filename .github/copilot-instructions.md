# Copilot Instructions (Canonical)

Adopt the **Lex** voice: direct, thoughtful, challenges assumptions. Be concise and show evidence.

## Big Picture
Local-first live captioning + EN↔ZH translation with:
- **CLI** entry points (e.g., `loquilex/cli/*`)
- **FastAPI WebSocket API** (`loquilex/api/server.py`) streaming partial/final events
- **Supervisor/session** pattern with bounded queues

## Environment & Config
- Use `LX_*` env vars only (e.g., `LX_ASR_MODEL`, `LX_DEVICE`, `LX_OUT_DIR`).
- Tests must be **offline**; use fakes/mocks instead of downloading models.

## Gates & Commands
- Default quick gate (no heavy ML):
  ```bash
  make run-ci-mode
  ```
- Heavier local parity when required:
  ```bash
  make run-local-ci
  ```
- Lint/format/typing must pass (Ruff, Black@100, mypy) before proposing a PR.

## Workflow
1. Read the relevant prompt file in `.github/prompts/` (e.g., `current-task.prompt.md`). Keep architecture changes minimal.
2. **Search the repo first** (ripgrep/grep) for similar functions/classes. Reuse patterns.
3. Propose focused changes; avoid new dependencies unless the task asks.
4. Record full logs/diffs/outcomes to the repo-root `current-task-deliverables.md` (gitignored); when the work rotates, copy the final state to `docs/deliverables/ARCHIVE/PR-<number>-<YYYYMMDD>-<shortsha>.md` and reset the root log.
5. Use `docs/deliverables/templates/deliverables-template.md` as the starting scaffold when creating or restoring the log.

## Conventions
- Commit messages in **imperative** mood.
- Minimal diffs; stable imports and ordering.
- No network access in tests; respect fakes and env guards.
- Do not change CI, secrets, or deployment unless explicitly requested.

## Git Etiquette
- Use **SSH** remotes.
- Default conflict strategy when merging main: `-X ours` (call out when `-X theirs` is correct).
- No force-push unless instructed. Prefer **squash merges**.

## VS Code Prompt Files
Prompt files live in `.github/prompts/` with front-matter (e.g., `mode: agent`, `model: GPT-5`).
Examples:
- `main.prompt.md` — primary operating instructions for Codex/Copilot.
- `make-fix.prompt.md` — quick remediation workflow.
- `make-fix-full.prompt.md` — fuller remediation workflow when context resets are needed.
- `current-task.prompt.md` — active task driver with deliverables logging reminders.
- `next-pr-runner.md` — follow-up checklist for PR grooming.

## Known Gotchas
- VS Code problemMatcher `$pytest` requires a defined matcher; prefer `make` targets for tests.
- Keep Markdown fences valid; avoid trailing whitespace to prevent ingestion issues.

## Forbidden Patterns
- Network calls in tests; implicit model downloads.
- Introducing new libraries or tools without a task mandate.
- Silent changes to core API/session contracts; if modified, update tests & docs.
- Editing out-of-scope files (e.g., CI, secrets, deploy) unless explicitly requested.
