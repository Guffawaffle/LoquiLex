---
mode: 'agent'
model: GPT-5
tools: ['runCommands', 'runTasks', 'edit', 'runNotebooks', 'search', 'todos', 'runTests', 'usages', 'vscodeAPI', 'problems', 'changes', 'testFailure', 'openSimpleBrowser', 'fetch', 'githubRepo', 'filesystem', 'create_branch', 'create_issue', 'create_pull_request', 'download_workflow_run_artifact', 'get_code_scanning_alert', 'get_commit', 'get_dependabot_alert', 'get_file_contents', 'get_global_security_advisory', 'get_job_logs', 'get_pull_request', 'get_pull_request_diff', 'get_pull_request_files', 'get_pull_request_review_comments', 'get_pull_request_reviews', 'get_pull_request_status', 'get_secret_scanning_alert', 'get_workflow_run', 'get_workflow_run_logs', 'get_workflow_run_usage', 'list_branches', 'list_code_scanning_alerts', 'list_commits', 'list_dependabot_alerts', 'list_global_security_advisories', 'list_issue_types', 'list_issues', 'list_org_repository_security_advisories', 'list_pull_requests', 'list_releases', 'list_secret_scanning_alerts', 'list_sub_issues', 'list_tags', 'list_workflow_jobs', 'list_workflow_run_artifacts', 'list_workflow_runs', 'list_workflows', 'push_files', 'remove_sub_issue', 'reprioritize_sub_issue', 'run_workflow', 'search_code', 'search_issues', 'search_orgs', 'search_pull_requests', 'search_repositories', 'update_issue', 'update_pull_request', 'update_pull_request_branch', 'memory', 'pylance mcp server', 'copilotCodingAgent', 'activePullRequest', 'openPullRequest', 'getPythonEnvironmentInfo', 'getPythonExecutableCommand', 'installPythonPackage', 'configurePythonEnvironment', 'configureNotebook', 'listNotebookPackages', 'installNotebookPackages']
description: 'Execute the repo’s current task and record full deliverables with real, minimal, verifiable evidence.'
---

#instruction
Execute the maintainer-provided task for this run (as described in the active prompt, issue, or conversation) while following all project rules in `AGENTS.md`.

#requirements
- Work only on the branch specified by the task spec (prompt/issue/conversation). **Never** use `main`.
- Honor the **offline-first** policy. Do not make network calls or download models unless the task explicitly permits it.
- Use existing Makefile/CI targets. Do not modify CI workflows, secrets, or repository settings unless the task requires it.
- If GitHub UI-only steps are needed, mark them **Manual Step Required** with an exact click path.
- Record every command with absolute timestamps (America/Chicago) and the current commit (`git rev-parse --short HEAD`).
- Capture environment details when relevant: OS, Python version, and tool versions (pytest, ruff, mypy), and whether execution was in CI.
- If a step fails, include full error output. Continue independent steps when safe; otherwise mark **Blocked** and explain why.
- Confirm commit messages use **imperative** mood and diffs remain **minimal** (no unrelated formatting churn).
- Link all relevant GitHub Actions run URLs/IDs.
- Do not expose secrets. Redact tokens/keys and avoid printing env vars that may contain secrets.
- **Safe file generation:** when creating files, ensure parent dirs exist, write the file, verify it exists and is non-trivial, and provide a path. Retry once if missing.

## Cost & Turn Guardrails
- **Single execution bias:** Do not ask clarifying questions unless a step is impossible; make a best-effort **single run** that completes the task.
- **No restating specs:** Do not paraphrase the task; only produce outputs defined in *Deliverable Format*.
- **Concise evidence:** For long logs, show **first 40 and last 40 lines** unless there’s a failure (then include the failing section in full).
- **Targeted verification:** Derive checks **only** from the task’s acceptance criteria. Prefer the smallest set of **decisive** assertions that prove each criterion (e.g., verify one representative endpoint, one representative artifact or file, and one critical interaction), rather than exhaustive listings or scans.
- **Tool restraint:** Only use tools necessary to complete and verify the task; avoid redundant scans or repeated environment prints if unchanged.

## Verification Strategy (task-agnostic)
For **each acceptance criterion** in the authoritative task spec:
1. Implement the change with a **minimal diff**.
2. Capture one **decisive verification** that proves the criterion (command output, test log, file header, grep result, etc.).
3. Prefer **positive assertions** (status OK, content-type match, test pass) over negative proofs.
4. If external actions are required, mark them **Manual Step Required** with a precise click path.

## Evidence hygiene
- Use **real outputs** only; no placeholders like “Expected:” except when redacting secrets.
- Prefer **file-specific** checks over directory listings.
- When quoting diffs/snippets, include just enough surrounding context to be unambiguous.

#deliverable-format
Write a single file: `docs/deliverables/.live.md` (gitignored), containing:

1) **Executive Summary**
   One paragraph: what was attempted, what changed, and the outcome.

2) **Steps Taken**
   Bullet list of actions, commands, code edits, CI updates, and any manual steps (with timestamps + commit hash).

3) **Evidence & Verification**
   - Full command outputs (pytest, mypy, ruff, etc.) with sensitive data redacted.
   - Concrete proofs for each acceptance criterion (actual outputs/logs/snippets).
   - Workflow run links (URLs/IDs) and relevant logs/stack traces.
   - Environment details collected above.

4) **Final Results**
   Explicit pass/fail against task goals. Remaining warnings/skips and follow-ups (link issues if created).

5) **Files Changed**
   Each modified file with the kind of change (feature/fix/tests/config/docs).

#output
Only write `docs/deliverables/.live.md`. No additional commentary or files.
