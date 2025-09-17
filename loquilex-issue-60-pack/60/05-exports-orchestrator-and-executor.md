# Exports Orchestrator + Thin Python Executor

Parent: #60

## Summary
Implement an **Exports** flow for transcripts (TXT/JSON/VTT/SRT). TS orchestrator manages export jobs and progress; backend executes file writes and reports progress via WS.

## Goals
- **UI (TS)**: `exportStore`; export dialog (format, range, options); job progress UI with cancel.
- **Backend (Py)**: `POST /exports/start` and WS `export.{progress|completed|failed}`; file validation; atomic writes.

## Acceptance Criteria
1. Export TXT/JSON/VTT/SRT successfully; progress visible; cancel works.
2. Errors (permission/disk) surfaced clearly.
3. e2e happy path and cancel path; CI green.

## Out of Scope
- Cloud uploads; advanced templating.
