# Contributing to LoquiLex

Thanks for helping! This project is **local-first** and must build/test **offline**.

## Developer Setup
1. Python 3.12
2. `pip install -r requirements-dev.txt`
3. Run: `ruff check . && black --check . && pytest -q -m "not e2e"`

## Tests
- **Unit**: default; fast & deterministic; no I/O or network.
- **E2E**: mark with `@pytest.mark.e2e`; localhost-only; provide fakes for ASR/MT.

## PR Checklist
- [ ] No compiled artifacts committed
- [ ] Tests added/updated
- [ ] Docs updated (README/CHANGELOG) if behavior changes
- [ ] Dev deps pinned

See **AGENTS.md** and `.github/copilot-instructions.md` for agent-aware guidance.