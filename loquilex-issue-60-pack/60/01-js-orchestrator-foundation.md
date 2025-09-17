# JS Orchestrator Foundation (stores, types, worker channel)

Parent: #60

## Summary
Establish a **JS-first** orchestration layer in React/TypeScript: shared utilities (retry/backoff), strict TS types for REST/WS contracts, and an optional **Web Worker** channel for progress/ETA smoothing. This becomes the standard pattern used by Downloads, Device Test, Exports, and Session flows.

## Goals
- Create `@/orchestration` module with:
  - **Stores** (Zustand/Redux) patterns and helpers (state machine utilities).
  - **Retry/backoff** helpers; concurrency limiter; cancellation tokens.
  - **WS client** wrapper with reconnect and bounded queues.
  - **Types** for REST/WS payloads (versioned contracts).
  - **Worker channel** (postMessage) for rate/ETA computations off main thread.

## Deliverables
- `orchestration/` directory with unit tests.
- Typed WS/REST client with pluggable handlers.
- Example reducer + dev story (storybook or MDX vignette) for usage.

## Acceptance Criteria
1. New module compiles with TS strict and has ≥80% unit test coverage.
2. WS wrapper supports reconnect, backpressure, and message typing.
3. Worker channel demo computes smoothed progress (2–10 Hz) without main-thread jank.
4. Contracts are defined in a single source-of-truth types file(s).
5. CI green (`make run-ci-mode`).

## Tests
- Unit: reducers, retry/backoff, concurrency limiter, worker channel.
- Integration (mocked): WS reconnect/backpressure paths.

## Out of Scope
- Feature-specific UI; handled in respective sub-issues.
