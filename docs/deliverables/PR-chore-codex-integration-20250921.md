Task: Conversation — 2025-09-22 Streamline Codex deliverables
SHA256: n/a (conversation)

**Git:** branch=chore/codex-integration, head=051da7d, base=origin/main@e72d90a
**Env:** Python 3.12.3; Ruff n/a (not in PATH); mypy n/a (not in PATH); OS=Ubuntu 24.04.3 LTS
**Mode:** Workspace-Only
**Network:** Offline (no model downloads)
**Secrets/CI:** Unchanged

## Executive Summary
- Removed reliance on `.github/copilot/current-task.md` in favor of prompt/conversation-driven specs across docs and prompts.
- Migrated deliverables template and this log to the new timestamped, append-only format with retained legacy history.

## Log

### 2025-09-21T22:41:56-05:00 — Streamline task source & deliverables
**Mode:** Workspace-Only
**Network:** Offline (no model downloads)
**Secrets/CI:** Unchanged

- Updated `AGENTS.md`, `README.md`, `PROJECT_OVERVIEW.md`, and `.github/prompts/main.prompt.md` to reference prompt/maintainer specs instead of `.github/copilot/current-task.md`.
- Refreshed `.github/copilot/deliverables-template.md` to capture task source metadata and append-only log guidance.
- Restructured `.github/copilot/current-task-deliverables.md` to the new template while preserving legacy entries below.
- Updated `.github/copilot/current-task.md` to a minimal stub pointing to the new workflow docs.
- Search receipt: `rg "current-task.md" -n` → no matches (confirms global deprecation).
- Search receipt: `rg "current-task-deliverables" -n AGENTS.md README.md PROJECT_OVERVIEW.md` → see evidence below.
- Committed `Streamline Codex deliverables workflow` (59c8bd0) and pushed `chore/codex-integration` to origin.

<details><summary>Environment fingerprints</summary>

```text
python3 --version
Python 3.12.3

ruff --version
bash: line 1: ruff: command not found

mypy --version
bash: line 1: mypy: command not found

lsb_release -ds
Ubuntu 24.04.3 LTS
```

</details>

<details><summary>Search receipts</summary>

```text
rg "current-task.md" -n
# no matches

rg "current-task-deliverables" -n AGENTS.md README.md PROJECT_OVERVIEW.md
AGENTS.md:85:* Maintain exactly one local `.github/copilot/current-task-deliverables.md` (gitignored). This is the live working log for the active branch.
README.md:108:- **Deliverables**: Live log in `.github/copilot/current-task-deliverables.md` (local, untracked) with archived snapshots under `docs/deliverables/`
PROJECT_OVERVIEW.md:28:- ✅ Copilot/Codex agents integrated: prompts in `.github/prompts/` drive execution, live logs kept locally in `.github/copilot/current-task-deliverables.md` with archives under `docs/deliverables/`.
PROJECT_OVERVIEW.md:60:  - Deliverables are logged locally in `.github/copilot/current-task-deliverables.md` and archived to `docs/deliverables/` when shared.

```

</details>

### 2025-09-21T22:45:38-05:00 — Ignore deliverables archive
**Mode:** Workspace-Only
**Network:** Offline (no model downloads)
**Secrets/CI:** Unchanged

- Updated local-only `.gitignore.local` to ignore `.github/copilot/current-task-deliverables.md` explicitly and the `.github/copilot/archive/` directory.
- Search receipt: `rg "archive/" .gitignore.local`

### 2025-09-21T22:53:17-05:00 — Archive deliverables snapshot
**Mode:** Workspace-Only  
**Network:** Offline (no model downloads)  
**Secrets/CI:** Unchanged

- Added `/.github/copilot/current-task-deliverables.md` to `.gitignore` so the live log stays local-only.
- Copied the current log to `docs/deliverables/PR-chore-codex-integration-20250921.md` for reviewers.
- Search receipt: `rg "current-task-deliverables" docs/deliverables -n`
- Committed `Archive deliverables log and ignore live file` (051da7d) and pushed `chore/codex-integration` to origin.

<details><summary>Legacy log (pre-2025-09-22)</summary>

## Executive Summary

Changed several GitHub Actions workflows to add an early step that disables Ubuntu ESM (Enterprise Security Maintainers) to prevent `apt` from contacting `esm.ubuntu.com`, which was blocked by the agent firewall and caused the Copilot coding agent to fail when running apt-related operations on Ubuntu runners. The change is safe for ephemeral CI runners and avoids requiring repo-level firewall allowlisting.


## 2025-09-21 — A11y Option A (Local-only) Completed

### Executive Summary
- Implemented Option A: keep Playwright a11y checks local-only (non-CI-gating), add explanatory comments, and stabilize a flaky delay in one test.
- Verified repo CI gates remain unchanged; ran All Checks locally — green.

### Changes Made
- Docs/Comments:
  - Added local-only scope notes at the top of `ui/app/src/test/e2e/settings-a11y.spec.ts`.
  - Confirmed `ui/app/playwright.a11y.config.ts` already documents non-gating behavior and preview server usage.
- Test Fix:
  - Replaced unsupported `delay` option in Playwright `route.fulfill` with an explicit `setTimeout`-style `await` to model network latency.

### Diffs
```diff
diff --git a/ui/app/src/test/e2e/settings-a11y.spec.ts b/ui/app/src/test/e2e/settings-a11y.spec.ts
@@
-import { test, expect } from '@playwright/test';
-import AxeBuilder from '@axe-core/playwright';
+import { test, expect } from '@playwright/test';
+import AxeBuilder from '@axe-core/playwright';
+// NOTE: This a11y spec is intended for local developer runs and not CI gating.
+// - Routes are mocked to avoid backend dependencies.
+// - The suite opens the Vite preview server via Playwright config.
+// - A couple of tests can be timing-sensitive in headless environments; avoid
+//   moving these into required CI gates without additional hardening.
@@
   test('settings page handles loading and error states accessibly', async ({ page }) => {
     // Test loading state
-    await page.route('/models/asr', route => {
-      // Delay response to test loading state
-      route.fulfill({
-        status: 200,
-        contentType: 'application/json',
-        body: JSON.stringify([]),
-        delay: 100
-      });
-    });
+    await page.route('/models/asr', async route => {
+      // Delay response to test loading state (Playwright doesn't support 'delay' in fulfill options)
+      await new Promise(resolve => setTimeout(resolve, 100));
+      await route.fulfill({
+        status: 200,
+        contentType: 'application/json',
+        body: JSON.stringify([])
+      });
+    });
```

### Verification
- Ran VS Code task: `All Checks`.
- Result (pytest): `237 passed, 3 skipped in 20.96s` (as reported in task output).
- No lint/typecheck regressions reported; exit code 0.

### Final Results
- Option A complete: a11y suite is documented as local-only and not part of CI gating.
- Flaky delay fixed in the a11y spec to improve local determinism.
- Next: open a follow-up issue to harden remaining flakes (focus order determinism, timing), and consider promoting stable a11y checks into CI later.

### Files Changed (this update)
- `ui/app/src/test/e2e/settings-a11y.spec.ts` (comments + delay fix)

Files changed (workflow edits):
- `.github/workflows/ci.yml`
- `.github/workflows/codeql.yml`
- `.github/workflows/dead-code-analysis.yml`
- `.github/workflows/dependency-review.yml`
- `.github/workflows/gitleaks.yml`
- `.github/workflows/rotate-task.yml`
- `.github/workflows/preexec-guard.yml`
- `.github/workflows/scorecards.yml`

What I did

- Inserted a standardized step after `Checkout` in each Ubuntu-based job that:
  - Runs `pro`/`ua` commands to disable ESM if available.
  - Removes the apt ESM hook and ESM source list files.
  - Comments out any `esm.ubuntu.com` lines in `/etc/apt/sources.list` (safe fallback).
  - Runs `apt-get update -y || true` to settle apt state.

Why this approach

- Disabling ESM on ephemeral runners is a minimal, reversible action that prevents network calls to `esm.ubuntu.com` which the agent environment blocks. It avoids requiring admin changes or allowlisting while keeping CI deterministic.

Full CI-parity run (commands executed locally):

Command run:

```
make docker-ci-test
```

Build output (summary):

```
DOCKER_BUILDKIT=1 docker build -f Dockerfile.ci -t loquilex-ci . --progress=plain
... (build succeeded)
```

Test output (summary):

```
=== Pytest (unit/integration) ===
226 passed, 4 skipped, 10 deselected in 23.03s

=== Pytest (e2e) ===
10 passed, 230 deselected in 3.30s

=== DONE: CI-parity run completed successfully ===
```

Representative logs (selected):

```
WARNING loquilex.api.ws_protocol: Flow control prevents sending MessageType.ASR_PARTIAL
ERROR   loquilex.api.ws_protocol: System heartbeat loop error: StopAsyncIteration
... many unit tests logged and passed; see repository CI run for full logs
```

Next steps

- I will commit these changes on branch `copilot/fix-100` and push to `origin` unless you ask me to change the commit message or target branch.

Files changed by this task (explicit list):
- `.github/workflows/ci.yml` (ESM-disable step added)
- `.github/workflows/codeql.yml` (ESM-disable step added)
- `.github/workflows/dead-code-analysis.yml` (ESM-disable step added)
- `.github/workflows/dependency-review.yml` (ESM-disable step added)
- `.github/workflows/gitleaks.yml` (ESM-disable step added)
- `.github/workflows/rotate-task.yml` (ESM-disable step added)
- `.github/workflows/preexec-guard.yml` (ESM-disable step added)
- `.github/workflows/scorecards.yml` (ESM-disable step added)

Full command outputs, diffs, and verification steps have been recorded above and can be reproduced locally using `make docker-ci-test`.

If you'd prefer the allowlist approach instead, ask your repository admin to add `esm.ubuntu.com` to the Copilot coding agent firewall allowlist and I can remove the workflow changes.

---

Deliverable generated by automated copilot agent patch on branch `copilot/fix-100`.

## Revert

Per your request, I reverted the workflow changes that injected the ESM-disable step. The workflows have been restored to the state in `origin/main`.

Revert commit: `cb52d81` (pushed to `copilot/fix-100`)

## Admin allowlist instructions (detailed)

You confirmed you are an admin. To avoid modifying workflows and still allow the Copilot coding agent to run apt-related steps that contact `esm.ubuntu.com`, add `esm.ubuntu.com` to the Copilot coding agent firewall allowlist.

Steps (GitHub UI)

1. Go to your repository on GitHub: `https://github.com/Guffawaffle/LoquiLex`.
2. Click `Settings` → `Code and automation` → `Copilot` (or use the left sidebar 'Copilot' entry if present).
3. Under 'Coding agents' (or 'Coding agent settings'), find 'Firewall allowlist' or similar.
4. Add the hostname:

```
esm.ubuntu.com
```

5. Save the settings. This allows the Copilot coding agent environment to reach `esm.ubuntu.com` without requiring workflow patches.

Steps (GitHub CLI / org admins)

If you prefer to use `gh` and you have admin privileges, you can verify settings via `gh` extensions or the REST API. There is no first-class `gh` subcommand that edits Copilot agent firewall allowlist as of this writing; you must use the UI or org-level admin APIs. If you want, I can build a small script that calls the GitHub REST API to update repository settings (you'll need a token with repo:admin scope).

Why allowlist is preferable

- Keeps workflows simple and avoids invasive host-level operations in CI jobs.
- Allows the agent to execute apt operations that may legitimately query ESM on Ubuntu runners.

If you want, I can now remove the deliverable entry that noted the earlier workflow edits and finalize the PR (or open a PR to merge the revert). What would you like next?

## 2025-09-22 — Refresh agent instructions for Codex integration

### Executive Summary
- Consolidated agent onboarding docs (root `AGENTS.md`, `.github/copilot-instructions.md`, prompt files) for the Codex workflow and removed the deprecated `.github/AGENTS.md` duplicate.

### Steps Taken
- Rewrote `AGENTS.md` to document operating modes, gates, guardrails, and deliverables expectations.
- Updated `.github/copilot-instructions.md` to match the new conventions and clarify prompt locations.
- Moved VS Code prompt files into `.github/prompts/` with front matter and cleaned up the legacy `.github/copilot/*.prompt.md` copies.
- Removed the unused `.github/AGENTS.md` stub (`rm .github/AGENTS.md`).

### Evidence & Verification
- Documentation-only refresh; no builds/tests required.

### Final Results
- Copilot/Codex guidance now points to a single source of truth with consistent prompts.

### Files Changed
- `AGENTS.md`
- `.github/copilot-instructions.md`
- `.github/prompts/main.prompt.md`
- `.github/prompts/make-fix.prompt.md`
- `.github/prompts/make-fix-full.prompt.md`
- `.github/AGENTS.md` (removed)

</details>
