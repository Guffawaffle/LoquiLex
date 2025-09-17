# Downloads Orchestrator + Thin Python Executor

Parent: #60

## Summary
Implement a **Downloads** flow: React/TS orchestrator owns queue/concurrency/pause-resume-cancel; Python/FastAPI performs actual bytes-on-disk with partials, checksum, and **WS progress**. Applies to ASR and Translation models.

## Goals
- **UI (TS)**: `downloadsStore` with states `queued|running|paused|completed|failed`, actions, and selectors. Downloads tab UI with repo select, type filter, search, list, and **job cards**.
- **Backend (Py)**: `/models/repos`, `/models/list`, `/models/download`, `/models/import`, `/models/jobs`, `/models/jobs/{id}` (DELETE), and WS events `model.download.{started|progress|completed|failed}`.
- **Persistence**: job registry survives restart; resume if possible; atomic finalize.
- **Offline-first**: import-from-disk when `LX_OFFLINE=1`.

## Acceptance Criteria
1. Start 2 downloads, pause 1, cancel 1; states are correct and UI reflects transitions.
2. Progress updates ≥2 Hz with rate/ETA smoothing; Reveal-in-folder works.
3. Disk/permission/network error messages are human-readable; license notice surfaced when provided.
4. Jobs survive restart; either resume or terminal state recorded.
5. CI green; unit/integration/e2e added.

## Tests
- UI unit: store transitions; reducer correctness.
- Backend integration: executor progress, cancel, resume paths.
- e2e: happy path and error scenarios.

## Out of Scope
- Advanced repo auth; model conversion.
