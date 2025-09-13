# LoquiLex — Copilot Instructions (Canonical)

> This is the **only** repo‑wide custom instructions file used by Copilot. Keep it at `.github/copilot-instructions.md`. Do not duplicate under subfolders. See official docs.

## Big Picture
Local-first live captioning + EN↔ZH translation:
- **CLI** (e.g., `loquilex/cli/live_en_to_zh.py`) for local runs
- **FastAPI WebSocket API** (`loquilex/api/server.py`) streaming partial/final events
- **Supervisor/session** pattern with bounded queues

## Environment & Config
- Prefer **`LX_*`** env vars; legacy **`GF_*`** are read for migration with a one‑time deprecation warning.
- Common: `LX_ASR_MODEL`, `LX_ASR_LANGUAGE`, `LX_DEVICE`, `LX_NLLB_MODEL`/`LX_M2M_MODEL`, `LX_OUT_DIR`, timing (`LX_PAUSE_FLUSH_SEC`, `LX_SEGMENT_MAX_SEC`).

## Day‑1 Commands
- **Lightweight CI‑parity (no heavy ML):**
  ```bash
  make run-ci-mode
  ```
- **Full local dev with ML deps:**
  ```bash
  make run-local-ci
  ```

## Testing Modes
- **Unit (offline):** Fakes in `tests/fakes/` injected via `tests/conftest.py` to prevent network/model downloads.
- **E2E (heavier):** Real models; run when end‑to‑end coverage is required.

## Conventions
- Black (100 cols) + Ruff; minimal diffs; imports ordered.
- mypy enabled; don’t regress typing quality.
- Commit messages in **imperative** mood.
- Offline‑first: no network calls in tests; respect fakes/envs.

## Task Source of Truth
- **Active:** `.github/copilot/current-task.md`
- **Fallback:** `.github/copilot/new-task-deliverables.md`
- Standard **deliverables** file: `.github/copilot/current-task-deliverables.md`

## Agent Workflow
1. Read the current task (above). Keep architectural changes minimal.
2. Run gates via Make: lint → format → typecheck → tests.
3. Record full logs, diffs, and outcomes to the deliverables file.

## Integration Notes
- WebSocket stream separates **partial** vs **final** transcript/translation events.
- Supervisor manages per‑session processes and cleanup with bounded queues.

## Prompts (VS Code)
Prompt files live in `.github/prompts/` with front‑matter (e.g., `mode: agent`, `model: GPT-4o`).
- `/run-current-task-4o` runs the task pinned to GPT‑4o.
- `/finish-and-rotate` verifies success and logs `bash .github/copilot/rotate-task.sh` output into deliverables.

## Gotchas
- VS Code tasks: avoid `$pytest` problemMatcher unless defined; use Make/CLI to run tests.
- Don’t introduce new `GF_*` usage; prefer `LX_*` and preserve one‑time deprecation behavior.

## Forbidden Patterns
- Network access in tests; implicit model downloads; hidden side effects.
- Bypassing env‑migration rules.
- Changing core API/session contracts without updating tests & docs.
