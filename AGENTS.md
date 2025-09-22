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
- **Cloud Sandbox (optional):** Allowed only if explicitly stated in `.github/copilot/current-task.md`. Clone, run, and test in an isolated sandbox; redact secrets; include full logs/diffs in deliverables.
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

* If `.github/copilot/current-task.md` exists, it is authoritative.
* Otherwise, follow the assigned issue’s acceptance criteria.

---

## Deliverables Policy

Always produce `.github/copilot/current-task-deliverables.md` as a running log.

**Deliverables format (required):**

1. **Executive Summary** — what was attempted, what changed, outcome.
2. **Steps Taken** — commands, diffs, edits.
3. **Evidence & Verification** — full outputs (lint/type/tests), logs, stack traces, before/after snippets.
4. **Final Results** — whether goals were met; remaining issues.
5. **Files Changed** — list with change types.

Use `.github/copilot/deliverables-template.md` as a starting point. Never truncate evidence; redact secrets if present.

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
