# Relaunch Matrix

This document defines which settings require restarting the application or backend service.

## Restart Scopes

Settings are categorized by their restart requirements:

- `none` - No restart required, changes take effect immediately
- `app` - Application restart required (frontend only)
- `backend` - Backend service restart required
- `full` - Both application and backend restart required

## Settings Matrix

| Setting | x-restart | Reason |
|---------|-----------|--------|
| `asr_model_id` | `backend` | ASR model changes require backend restart to unload/load models |
| `mt_model_id` | `backend` | MT model changes require backend restart to unload/load models |
| `device` | `backend` | Device changes (CPU/GPU) require backend restart to reinitialize models |
| `cadence_threshold` | `none` | Word count threshold can be changed dynamically |
| `show_timestamps` | `none` | UI display setting, changes immediately |

## UI Behavior

### Badges
Settings with `x-restart != "none"` display restart badges:
- Backend restart required: Orange badge "Restart Required"
- App restart required: Blue badge "App Restart Required" 
- Full restart required: Red badge "Full Restart Required"

### Apply & Relaunch Action
- When settings with restart requirements are changed, show "Apply & Relaunch" button
- Button queues all pending changes
- On click, applies changes and triggers appropriate restart scope
- Shows confirmation dialog before restart

## Implementation Notes

- Badge visibility is based on the `x-restart` field in settings schema
- Changes are queued until "Apply & Relaunch" is clicked
- Regular "Save Settings" button continues to work for `x-restart: "none"` settings
- Restart flow should preserve session state where possible