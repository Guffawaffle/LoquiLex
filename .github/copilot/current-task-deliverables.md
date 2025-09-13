# Security Epic #16 — Part 1: CodeQL + Dependency Review (Draft)

## Executive Summary
Implemented two GitHub Actions workflows—CodeQL (Python & JS) and Dependency Review—per acceptance criteria. Local YAML validation passed. Cloud verification (runs, Security tab, and sample PR gating) will be executed once we push this branch.

## Steps Taken
- Created `.github/workflows/codeql.yml` (author: Lex) to scan Python & JS on PRs to `main`, pushes to `main`, and a weekly cron.
- Created `.github/workflows/dependency-review.yml` (author: Lex) to fail PRs on **high**-severity advisories and post a PR summary comment.
- Added repo `.yamllint.yaml` to scope linting to Actions and ignore venvs; lint rules tuned for GH expressions.
- Validated locally with `yamllint .github/workflows` (no findings).

## Evidence & Verification
- **YAML lint**: `yamllint .github/workflows` → _no output_ (pass).
- **Env**: Python 3.12.3 via direnv venv at `.direnv/python-3.12.3`.
- **Files**: Workflows include author header comments attributing Lex.

> Cloud verification pending push:
> - CodeQL run links (push + PR + cron)
> - Dependency Review PR comment + red X when high-severity found
> - Security tab shows CodeQL enabled

## Final Results
- Local validation: ✅
- Cloud verification: ⏳ (to be completed after push)
- Follow-ups: create a sample PR that introduces a known **high-severity** vulnerable dependency to confirm gating.

## Files Changed
- `.github/workflows/codeql.yml` — new
- `.github/workflows/dependency-review.yml` — new
- `.yamllint.yaml` — new
