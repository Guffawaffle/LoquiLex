---
name: 'Feature request: loquilex.config'
about: Proposal to introduce a centralized runtime configuration module `loquilex.config`.
title: 'Feature: loquilex.config - centralized runtime settings'
labels: enhancement
assignees: ''
---

## Summary

Introduce a centralized configuration/settings module `loquilex.config` to host runtime defaults (env-var backed), typed settings, and convenience helpers. This will replace ad-hoc module-level constants (like memory fallbacks) and make overrides, testing, and documentation consistent across the codebase.

## Motivation

- Reduce duplication of environment-var parsing and defaults across modules.
- Make unit testing easier by allowing import-time patching of a single config object.
- Standardize names, types, and docstrings for configuration values.

## Proposed Scope

- Create `loquilex/config.py` exposing a typed `Settings` dataclass or pydantic BaseSettings (opt-in) with fields such as:
  - `fallback_memory_total_gb: float`
  - `fallback_memory_available_gb: float`
  - `min_memory_gb: float`
  - `min_cpu_cores: int`
  - `max_cpu_usage_percent: float`
  - `min_gpu_memory_gb: float`
- Update `loquilex.hardware.detection` to import values from `loquilex.config`.
- Provide a small migration guide and backwards-compatible env var names.

## Acceptance criteria

- `loquilex/config.py` exists and is importable.
- `loquilex.hardware.detection` imports settings from the new module and uses them.
- Tests (or a smoke-check) demonstrate being able to override settings via env vars and via monkeypatch.
- No behaviour change when env vars are not set.

## Migration notes

- Start by adding the module and leave old module-level constants in place; switch modules to import from `loquilex.config`.
- Update tests to patch `loquilex.config` values instead of module constants.

## Risks and mitigations

- Risk: introducing a new dependency (pydantic) — mitigation: implement a minimal typed dataclass fallback and avoid new deps unless requested.

## Timeline

- 1 day: add `loquilex.config` and switch `hardware.detection` to use it.
- 1 day: update tests and docs.

## Implementation notes

- Keep env var names consistent with existing `LX_*` prefix.
- Add clear docstrings and examples in `docs/feature_proposals/loquilex-config.md`.
