# Model Selection Dropdowns + Session/Launch Gating

Parent: #60

## Summary
Replace list selectors with **dropdowns** for ASR and Translation everywhere (Landing, Settings, Launch Wizard). Gate session start based on device/model presence as known to TS stores.

## Goals
- UI: dropdown components with keyboard/focus/ARIA; persist selections; show license badges if available.
- Session gating: disable Start/Continue if required models absent or device incompatible; provide guidance.

## Acceptance Criteria
1. Dropdowns render and persist across reload.
2. Keyboard nav and focus rings verified; screen reader labels present.
3. Session gating works as expected with clear messaging.
4. e2e smoke for selection + reload; CI green.

## Out of Scope
- Major layout changes; stick to existing dark theme and tokens.
