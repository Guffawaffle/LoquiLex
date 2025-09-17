# WS Resilience & Snapshot Rehydrate in TS

Parent: #60

## Summary
Harden the TS WS client: auto-reconnect with backoff, bounded queues, and **snapshot rehydrate** so UI state recovers after reload/crash.

## Goals
- Add reconnect/backoff strategy; drop/merge stale messages; idempotent handlers.
- Persist minimal snapshot of orchestrator state; restore on reload.
- Health indicators and error toasts.

## Acceptance Criteria
1. Reconnect after simulated server restart without losing job state.
2. Bounded queues prevent runaway memory usage.
3. Snapshot rehydrate verified via e2e.
4. CI green.

## Out of Scope
- Server clustering; handled separately.
