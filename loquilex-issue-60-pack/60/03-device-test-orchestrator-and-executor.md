# Device Test Orchestrator + Thin Python Executor

Parent: #60

## Summary
Provide a **Device Test** panel: UI triggers a quick probe + tiny ASR/MT run via backend, streaming `device.test.*` events. Return a JSON report and allow export.

## Goals
- **UI (TS)**: `deviceTestStore` with simple state and result typing; panel UI with "Run test" and result view; **Export JSON** button.
- **Backend (Py)**: `POST /device/test` and WS `device.test.{progress|completed|failed}`; detect CPU/GPU backends (CUDA/ROCm/DirectML) and memory; run minimal test graphs.

## Acceptance Criteria
1. Returns JSON report with device, backend, load_ms, tokens/s or xRT, and latency_ms.
2. Works offline (skips network); honors env flags; no large downloads.
3. Export JSON works; report saved.
4. Unit/integration/e2e added; CI green.

## Out of Scope
- Full benchmarking suite; just a quick probe.
