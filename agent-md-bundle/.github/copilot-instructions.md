# Repository custom instructions for GitHub Copilot

Applies to **Copilot Coding Agent**, **Copilot Chat**, and **Copilot Code Review**.

## Overview
LoquiLex is a local-first live captioning & translation system. **Never require outbound network** during build/tests. Use deterministic tests with mocks for ASR/MT.

## How to run
- Python 3.12
- `pip install -r requirements-dev.txt`
- Unit tests: `pytest -q -m "not e2e"`
- E2E (localhost-only): `pytest -q -m e2e`

## Style & Quality
- Lint: `ruff check .`
- Format: `black .`
- Types: `mypy loquilex` (warn-only until enforced)

## Conventions
- Separate partial vs final events.
- Keep CI jobs split: lint → typecheck → unit → e2e (offline).

## Forbidden
- Adding compiled artifacts (`__pycache__`, `*.pyc`).
- Adding steps that fetch models at test-time.