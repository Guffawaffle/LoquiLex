# Title
Security Epic #16 — Part 1: CodeQL + Dependency Review

## Context
Align repo with GH security scanning. This step adds CodeQL + Dependency Review only.

## Changes to Implement
- [ ] Add `.github/workflows/codeql.yml` for {python, javascript}, PRs to main, push to main, weekly cron.
- [ ] Add `.github/workflows/dependency-review.yml` that blocks ≥ high severity and posts PR summary.

## Acceptance Criteria
- [ ] Both workflows pass on this PR.
- [ ] Security tab shows CodeQL scanning enabled.
- [ ] A sample PR shows Dependency Review comment and gating behavior.

## Commands
- Use `make run-ci-mode` locally if needed; otherwise rely on CI.
- Record links to workflow runs in deliverables.

## Deliverables
Write full results to `.github/copilot/current-task-deliverables.md` (exec summary, steps, evidence/logs, results, files changed).
