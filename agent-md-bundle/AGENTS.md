# AGENTS.md — LoquiLex

> Custom instructions for GitHub Copilot **Coding Agent** (public preview).  
> Scope: Repository-wide defaults. Nested `AGENTS.md` may refine behavior per subdir.

## Project Primer
- **Name**: LoquiLex — live captioning & translation.
- **Core values**: local-first, offline-capable, reproducible, testable, accessible.
- **Stack**: Python 3.12, FastAPI + WebSockets, CTranslate2 for NLLB/M2M, Whisper (CT2), optional UVicorn.
- **Latency goals**: partials < 200ms; finals 500–800ms.
- **Artifacts**: TXT/JSON/VTT/SRT; optional WAV. No SaaS at runtime.

## Build & Test
- Use a **fully offline** test strategy. Do **not** reach the network (CI enforces localhost-only firewall).
- Unit tests: `pytest -q -m "not e2e" --maxfail=1`  
  E2E tests: `pytest -q -m e2e --maxfail=1`
- Provide fakes/mocks for ASR/MT components. Prefer dependency injection over patching.
- Do not include compiled artifacts (`__pycache__/`, `*.pyc`) in commits.

## Coding Guidelines
- Type hints everywhere; docstrings compatible with **PHPStan-style clarity** is not required here, but docblocks should be precise.
- Lint with **ruff**; format with **black**.
- Keep WebSocket clients/servers resilient: reconnect, snapshot rehydrate, bounded queues, monotonic time.
- Separate partial vs final events in schemas.

## PR Expectations
- Keep diffs minimal. No unrelated reformatting.
- Update **CHANGELOG.md** when changing behavior or configs.
- Update **/docs/** if flags, env vars, or routes change.
- Add/adjust tests for any new behavior. Prefer fast unit tests; mark slow/system with `@pytest.mark.e2e`.

## Security & Privacy
- No hardcoded tokens. No telemetry. Respect local-only constraints.
- When adding dependencies, prefer **pinned versions** and reproducible installs.

## Agent-Specific Behaviors
- When asked to “add tests,” default to **unit tests** with small, deterministic fixtures.
- When asked to “optimize,” measure first; add a micro-benchmark or profile note in the PR.
- When editing CI, keep **offline-first** and separate **lint/type/unit/e2e** jobs.