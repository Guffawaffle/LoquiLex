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
* Active prompt files live under `.github/prompts/`: `main.prompt.md`, `make-fix.prompt.md`, `make-fix-full.prompt.md`, `current-task.prompt.md`, and `next-pr-runner.md`.

---

## Deliverables Policy

* Maintain exactly one local `docs/deliverables/.live.md` (gitignored). This is the ephemeral working log for the active branch.
* When a PR merges, a hand-off occurs, or reviewers need the state, copy the log to `docs/deliverables/ARCHIVE/PR-<number>-<YYYYMMDD>-<shortsha>.md` (tracked) and share context in the PR notes; reset or remove the root log afterward so the next task starts clean.
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
* Use `docs/deliverables/templates/deliverables-template.md` as the canonical scaffold for new entries; update the template if the policy evolves.

Treat `docs/deliverables/.live.md` as scratch space during execution. When the work rotates or merges, capture the final state in the archive path and clear the live file so the next assignee starts with a blank log.

---

## Merge-Weave Strategy (Multi-PR Orchestration)

**Use this when:** Multiple related PRs are ready for integration and you want to parallelize independent work while minimizing conflicts.

**Critical principle:** Each PR should be **structurally independent** (can be reviewed, tested, and merged in isolation). They may have **logical dependencies** (PR B uses code from PR A), but each PR should not require another PR's branch to test or review. This allows them to be built in parallel, then merged together on `main`.

*Analogy: Build 4 car frame sections in parallel, then assemble them together.*

### Overview

**Merge-weave** is a **topologically-ordered pyramid** approach to integrating multiple dependent PRs:
- **Dependency graph:** Model PRs as a DAG (directed acyclic graph) where edges indicate "PR A must merge before PR B"
- **Topological sort:** Order PRs so leaves (no dependents) merge first, then parents (dependents) merge in sequence
- **Integration branch:** Use a staging branch (`merge-weave`) to aggregate leaves before landing on `main`
- **Parallel execution:** Independent PRs at the same dependency level can be processed in parallel

### When to Use

1. **Multiple independent PRs:** e.g., npm setup, CI/CD, health endpoint—each builds separately but combines on `main`
2. **Structural independence, logical layers:** Each PR is self-contained; they may logically depend on each other but don't need to be reviewed/tested sequentially
3. **High merge risk:** Staging aggregation reduces risk of partial merges from corrupting `main`
4. **Checkpoint control:** Each merge to weave is a checkpoint; close issues/PRs after leaves integrate and after final weave→main

### Process

#### 1. **Dependency Analysis**
```bash
# Map all open PRs and their dependencies
# Create a mental/documented dependency graph:
#   Level 0 (leaves): PR #A, PR #B (independent)
#   Level 1: PR #C depends on A or B
#   Level 2: PR #D depends on C
```

#### 2. **Create Integration Branch**
```bash
git fetch origin
git checkout -b merge-weave origin/main
# This branch is your staging area for leaves
```

#### 3. **Merge Leaves (Independent PRs)**
Since all leaves are independent, merge them all to the weave branch (in any order; it doesn't matter):
```bash
# Checkout weave branch
git checkout merge-weave

# For each leaf PR (order is irrelevant; they're independent):
git merge origin/<leaf-branch-1> --squash
git commit -m "merge: integrate <leaf-pr-1-description>"

git merge origin/<leaf-branch-2> --squash
git commit -m "merge: integrate <leaf-pr-2-description>"

git merge origin/<leaf-branch-N> --squash
git commit -m "merge: integrate <leaf-pr-N-description>"

# Verify CI passes on merge-weave (with all leaves together)
make run-ci-mode  # or Docker CI

# Push the updated weave branch
git push origin merge-weave

# Close leaf PRs/issues as checkpoints
# (via GitHub UI or gh pr close <numbers>)
```

#### 4. **Validate Weave Branch**
```bash
# Once all leaves merged to weave, run final comprehensive tests
make docker-ci-build && make docker-ci-test

# Or full local CI parity
make run-local-ci
```

#### 5. **Merge Weave to Main**
```bash
git checkout main
git pull origin main
git merge merge-weave --squash
git commit -m "merge: integrate merge-weave batch (leaves: #A, #B, ...)"
git push origin main

# Delete the weave branch (optional, for cleanup)
git push origin --delete merge-weave
```

#### 6. **Rebase & Merge Parents (Sequential)**
For each parent PR (in dependency order):
```bash
git checkout <parent-branch>

# Rebase on new main (which includes merged leaves)
git merge origin/main  # or git rebase origin/main

# Verify CI passes
make run-ci-mode

# Merge to main
git checkout main
git pull origin main
git merge <parent-branch> --squash
git commit -m "merge: integrate <parent-pr-description> (depends on <leaves>)"
git push origin main

# Close the parent PR/issue
```

### Conflict Handling

**In the weave branch:**
- **Trivial conflicts** (append-only files like `CHANGELOG.md`, docs): Use `git merge -X ours` and combine manually
- **Code conflicts:** Merge leaves sequentially; if conflicts arise, resolve and push updated weave branch; retest
- **Dependency order:** If PR A and PR B both modify `package.json`, ensure they're at the **same level** (both leaves or both parents); if one depends on the other, merge the leaf first

**When rebasing parents:**
- Use `git merge origin/main` (not rebase, to preserve history)
- Conflicts should be minimal if leaves don't overlap with parents
- If conflicts occur, apply `git merge -X ours` for code, manual combine for configs

### Gotchas & Best Practices

1. **Commit messages matter:** Use clear imperative messages (`merge: integrate X`) so the git log is readable
2. **No force-push on weave:** The weave branch is shared staging; don't rewrite its history
3. **Test aggressively:** Run CI after each leaf merge to catch issues early
4. **Close PRs incrementally:** Close leaves as soon as they're integrated to weave; close parents after they merge to main. This gives clear checkpoints.
5. **Dependency accuracy is critical:** Mislabeled dependencies will cause merge failures or hidden regressions. Double-check the graph before starting.

### Example: Three-Level Pyramid

**Dependency structure:**
```
         [main]
          |
    [merged leaves batch]
         /  |  \
    PR #155 PR #156 PR #157
    (health) (docs) (CI/CD)

    All independent: can be built in parallel
```

**Merge order (parallel batching):**
```bash
# 1. Create weave branch
git checkout -b merge-weave origin/main

# 2. Merge all leaves to weave (can do in any order, parallel or sequential—doesn't matter)
git merge origin/feature/health --squash         # PR #155
git commit -m "merge: integrate health endpoint"
git merge origin/feature/docs --squash           # PR #156
git commit -m "merge: integrate API documentation"
git merge origin/feature/ci --squash             # PR #157
git commit -m "merge: integrate CI/CD workflows"

# 3. Test merge-weave with all three together
make docker-ci-build && make docker-ci-test

# 4. Push weave branch
git push origin merge-weave

# 5. Merge weave → main (all three land together)
git checkout main && git pull origin main
git merge merge-weave --squash
git commit -m "merge: integrate merge-weave batch (leaves: #155, #156, #157)"
git push origin main

# 6. Close all three PRs/issues as checkpoints
gh pr close 155 156 157
```

### Rollback Strategy

If something goes wrong:
1. Delete the weave branch: `git push origin --delete merge-weave`
2. Reopen closed PRs (via GitHub UI)
3. Start fresh with a corrected dependency graph

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
