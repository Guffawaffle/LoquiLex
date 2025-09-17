---
mode: 'agent'
model: GPT-5
tools: ['runCommands', 'runTasks', 'edit', 'runNotebooks', 'search', 'todos', 'runTests', 'usages', 'vscodeAPI', 'problems', 'changes', 'testFailure', 'openSimpleBrowser', 'fetch', 'githubRepo', 'filesystem', 'create_branch', 'create_issue', 'create_pull_request', 'download_workflow_run_artifact', 'get_code_scanning_alert', 'get_commit', 'get_dependabot_alert', 'get_file_contents', 'get_global_security_advisory', 'get_job_logs', 'get_pull_request', 'get_pull_request_diff', 'get_pull_request_files', 'get_pull_request_review_comments', 'get_pull_request_reviews', 'get_pull_request_status', 'get_secret_scanning_alert', 'get_workflow_run', 'get_workflow_run_logs', 'get_workflow_run_usage', 'list_branches', 'list_code_scanning_alerts', 'list_commits', 'list_dependabot_alerts', 'list_global_security_advisories', 'list_issue_types', 'list_issues', 'list_org_repository_security_advisories', 'list_pull_requests', 'list_releases', 'list_secret_scanning_alerts', 'list_sub_issues', 'list_tags', 'list_workflow_jobs', 'list_workflow_run_artifacts', 'list_workflow_runs', 'list_workflows', 'push_files', 'remove_sub_issue', 'reprioritize_sub_issue', 'run_workflow', 'search_code', 'search_issues', 'search_orgs', 'search_pull_requests', 'search_repositories', 'update_issue', 'update_pull_request', 'update_pull_request_branch', 'memory', 'pylance mcp server', 'copilotCodingAgent', 'activePullRequest', 'openPullRequest', 'getPythonEnvironmentInfo', 'getPythonExecutableCommand', 'installPythonPackage', 'configurePythonEnvironment', 'configureNotebook', 'listNotebookPackages', 'installNotebookPackages']
description: 'Execute the repo’s current task and record full deliverables.'
---

#instruction
Execute the task described in `.github/copilot/current-task.md` while following all project rules in `AGENTS.md`.

#requirements
- Work only on the branch specified in `current-task.md` (create/switch as instructed). Never use `main`.
- Honor the offline-first policy. Do not make network calls or download models unless the task explicitly permits it.
- Use existing Makefile/CI targets as defined. Do not modify CI workflows, secrets, or repository settings unless the task requires it.
- If GitHub UI-only steps are needed, mark them as **Manual Step Required** with an exact click path.
- Record every command executed with absolute timestamps (America/Chicago) and the current commit (`git rev-parse --short HEAD`).
- Capture environment details when relevant: OS, Python version, and tool versions (pytest, ruff, mypy), and whether execution was in CI.
- If a step fails, include full error output. Continue with independent steps when safe; otherwise mark **Blocked** and explain why.
- Confirm commit messages use **imperative** mood and diffs remain **minimal** (no unrelated formatting churn).
- Link all relevant GitHub Actions run URLs/IDs.
- Do not expose secrets. Redact tokens/keys and avoid printing environment variables that may contain secrets.

#deliverable-format
Write a single file: `.github/copilot/current-task-deliverables.md`, containing:

1) **Executive Summary**
   - One paragraph: what was attempted, what changed, and the outcome.

2) **Steps Taken**
   - Bullet list of actions, commands, code edits, CI updates, and any manual steps.

3) **Evidence & Verification**
   - Full command outputs (pytest, mypy, ruff, etc.) with sensitive data redacted.
   - Before/after diffs or code snippets.
   - Workflow run links (URLs/IDs) and relevant logs/stack traces.
   - Environment details collected above.

4) **Final Results**
   - Explicit pass/fail against task goals.
   - Remaining warnings/skips and follow-up recommendations (link issues if created).

5) **Files Changed**
   - Each modified file with the kind of change (tests, annotations, config, CI).

#output
Only write `.github/copilot/current-task-deliverables.md`. No additional commentary or files.
