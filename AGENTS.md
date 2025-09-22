# AGENTS.md

This repository uses AI coding agents under human review.

## Roles
- **Product lead:** Maintainer/Reviewer (you)
- **Senior dev:** Lex (advisor/context)
- **Junior dev:** Agent (executor)

Agents MUST follow the workflow and guardrails below.

---

## Operating Modes (must declare which one)
- **Workspace-Only (default):** Edit files in this repo only. No network calls beyond fetching existing deps already pinned in lockfiles. No secret edits.
- **Cloud Sandbox (optional):** Allowed only if the active task spec (prompt, issue, or maintainer directive) explicitly authorizes it. Clone, run, and test in an isolated sandbox; redact secrets; include full logs/diffs in deliverables.
- **Full Access:** **Prohibited** unless explicitly granted in the current task.

---

## Setup (task-agnostic)
```bash
python3 -m venv .venv
. .venv/bin/activate
[ -f requirements.txt ] && pip install -r requirements.txt
[ -f package.json ] && npm ci
[ -f composer.json ] && composer install --no-interaction
```

## Build

```bash
# If no build is required, state that clearly.
echo "No build step"
```

## Test & Gates

* Run the project’s **lightweight CI parity**:

  ```bash
  make run-ci-mode || true
  ```
* If the task requires heavier checks:

  ```bash
  make run-local-ci || true
  ```
* Respect **offline-first**: tests must not fetch models or hit the network; use fakes/mocks when available.
* Gates must be **green** before a PR is “ready”: lint/format, typing, unit tests (and e2e when requested).

---

## Quality Rules

* **Minimal, focused diffs**: only files in scope.
* **Valid Markdown**: no broken fences, no trailing whitespace.
* **POSIX-friendly shell** for scripts.
* **No dependency upgrades** or toolchain changes unless the task explicitly asks.

---

## Git / PR Rules

* **Remotes:** Prefer SSH; do not switch to HTTPS.
* **Merge strategy (default):** When syncing `origin/main` into a feature branch, use `git merge -X ours origin/main`. If the intent is to prefer main, explicitly use `-X theirs`.
* **No force-push** unless explicitly instructed.
* **Commit style:** Imperative mood (`Add…`, `Fix…`, `Update…`).
* **Squash merge** preferred.
* **PR description must include:** WHAT changed, WHY it changed, and task reference.
* **Do not edit secrets/CI/deploy** unless explicitly instructed.

---

## Source of Truth

* The maintainer-provided task spec (prompt file, issue/PR description, or direct instruction) is authoritative.
* Record the exact source (path or URL) and digest at the top of the deliverables log so reviewers can trace what was executed.
* If the spec changes mid-task, add a new timestamped log entry noting the update and the new digest.

---

## Deliverables Policy

* Keep exactly one `.github/copilot/current-task-deliverables.md` on the active feature branch. When a PR merges or the task rotates, archive it (e.g., move to `docs/deliverables/PR-<number>-<YYYYMMDD>.md`) or capture the executive summary/evidence links in the PR description before starting a new log.
* Top of file requirements:
  - `Task:` include the authoritative source (e.g., `.github/prompts/next-pr-runner.md`, issue/PR URL, or “Conversation — YYYY-MM-DD”).
  - `SHA256:` hash of the source file if stored in the repo (`sha256sum <file>`). Use `n/a` when the spec is conversational or remote-only.
  - Quick fingerprints: `**Git:** branch=…, head=…, base=origin/main@…` and `**Env:** Python …; Ruff …; mypy …; OS=…`.
  - Current scope declaration: `**Mode:** …`, `**Network:** …`, `**Secrets/CI:** …` (update whenever scope changes).
* Maintain `## Executive Summary` at the top; keep it concise and updated as work progresses.
* Append-only log format:
  - Use a `## Log` section.
  - Each entry starts with `### <ISO8601 timestamp with offset> — <scope>`.
  - Immediately restate scope (`**Mode:** …`, `**Network:** …`, `**Secrets/CI:** …`).
  - Capture actions as bullets; include command timestamps and commit hashes when relevant.
  - When reusing patterns, include a “Search receipt” line showing the grep command and hit paths (no contents).
  - Wrap long outputs, diffs, or logs in `<details>` blocks with a succinct `<summary>` (include line counts when possible).
* Evidence must be real, complete outputs; redact secrets only. Avoid truncating unless the `<details>` wrapper is used.
* Use `.github/copilot/deliverables-template.md` as the canonical scaffold for new entries; update the template if the policy evolves.

---

## Guardrails

* Never run destructive commands.
* Never delete or edit out-of-scope files.
* If acceptance criteria are unclear, open questions in the PR — do not guess.
* Search the repo for existing patterns before proposing new APIs/tools.
* If a task seems too large or complex, break it down and seek approval before proceeding.
* If blocked, push a draft PR labeled `blocked` with details in the deliverables file.
* Always respect the project’s existing conventions and style.
* Do not bypass environment variable rules or introduce hidden side effects.
* Do not change core API/session contracts without updating tests and documentation.
* Do not introduce network calls in tests or implicit model downloads.
