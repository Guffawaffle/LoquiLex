# Agent Charter

## Allowed Tasks
- Bug fixes, small features, tests, refactors, docs, CI improvements.
- UI polish that stays within design tokens/components.

## Disallowed
- Secrets, infra changes outside repo, irreversible deletions.

## How to Work
1) Read issue goal + acceptance criteria.
2) Plan small steps; prefer multiple small PRs over one huge PR.
3) Run tests locally (or CI) before opening PR.
4) Open a PR with a clear summary and list of changes.

## Commands (reference)
- `npm test` / `pytest` / `ruff` / `mypy` (adjust to the repo)
- `make test` / `make lint` if available
