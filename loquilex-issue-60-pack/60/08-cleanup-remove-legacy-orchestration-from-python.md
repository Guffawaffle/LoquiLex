# Cleanup: Remove Legacy Orchestration from Python

Parent: #60

## Summary
After adopting TS orchestrators, prune redundant orchestration from Python services. Keep Python executors and model runtimes only.

## Goals
- Identify dead/duplicated orchestration.
- Remove or deprecate with clear notes and migration references.

## Acceptance Criteria
1. No duplicate orchestration between TS and Python.
2. CI green; tests updated.
3. CHANGELOG updated.
