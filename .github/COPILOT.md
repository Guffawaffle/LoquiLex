# Copilot Repository Instructions

## Mission
Implement tasks safely and incrementally with clear PRs. Follow repo conventions and don’t remove core functionality.

## Rules
- Touch **only** the scoped areas described in each issue.
- Add/update tests for every change; keep coverage at least as high as baseline.
- Keep diffs minimal and readable; explain WHY in the PR description.
- Never commit secrets; use env vars/placeholders.
- If a contract is unclear, open a small “question” commit or add PR comments instead of guessing.

## Quality Gates
- All CI jobs green: test, lint, type-check.
- Docs updated when behavior changes.
- Follow semantic commits (feat/fix/chore/docs/test/refactor/perf/build/ci).
