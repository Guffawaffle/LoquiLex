# Migration Guide: Legacy Orchestration to JS-First Architecture

## Overview

This guide documents the deprecation of legacy Python orchestration patterns in favor of the JS-first architecture where TypeScript orchestrates and Python provides execution services.

**Related Issue:** [#60 Cleanup: Remove Legacy Orchestration from Python](https://github.com/Guffawaffle/LoquiLex/issues/60)

## What Changed

### Deprecated Components

1. **`loquilex.api.supervisor.Session` class** (subprocess-based orchestration)
   - Spawns CLI orchestrators as subprocesses
   - Duplicates orchestration logic that TS should handle
   - Status: **DEPRECATED** - will be removed in a future release

2. **`loquilex.cli.live_en_to_zh`** (CLI orchestrator)
   - Standalone orchestration of audio → ASR → MT → output
   - Used as subprocess by legacy Session class
   - Status: **DEPRECATED** - will be removed in a future release

3. **`loquilex.cli.demo`** (CLI orchestrator)
   - Standalone demo orchestrating StreamingASR → MT → files
   - Status: **DEPRECATED** - will be removed in a future release

### Recommended Components

1. **`loquilex.api.supervisor.StreamingSession`** - In-process execution
   - Runs ASR/MT in-process without subprocess overhead
   - Designed to be orchestrated by external layer (TypeScript)
   - Status: **ACTIVE** - recommended pattern

2. **TypeScript orchestration layer** (see `docs/architecture/js-first.md`)
   - Controls workflow, state management, user interactions
   - Calls Python executor services via WebSocket API
   - Status: **ACTIVE** - primary orchestration pattern

3. **Python executor services:**
   - `loquilex.asr.stream.StreamingASR` - ASR processing
   - `loquilex.mt.service.MTService` - Translation
   - `loquilex.audio.capture` - Audio input
   - Status: **ACTIVE** - core execution services

## Migration Paths

### For API Server Usage

**Before (deprecated):**
```python
from loquilex.api.supervisor import SessionConfig, SessionManager

cfg = SessionConfig(
    streaming_mode=False,  # Spawns subprocess!
    # ... other config
)
manager = SessionManager()
sid = manager.start_session(cfg)  # Creates Session subprocess
```

**After (recommended):**
```python
from loquilex.api.supervisor import SessionConfig, SessionManager

cfg = SessionConfig(
    streaming_mode=True,  # In-process execution
    # ... other config
)
manager = SessionManager()
sid = manager.start_session(cfg)  # Creates StreamingSession
```

### For CLI Usage

**Before (deprecated):**
```bash
# Direct CLI orchestration
python -m loquilex.cli.live_en_to_zh --seconds 60
python -m loquilex.cli.demo --duration 30
```

**After (recommended):**
Use TypeScript orchestration:
```typescript
// TypeScript orchestrates via WebSocket API
import { createCaptionSession } from '@/orchestration'

const session = await createCaptionSession({
  source: 'microphone',
  language: 'en',
  translate: true
})

await session.start()
```

### For Direct Python Integration

**Before (deprecated):**
```python
# Running CLI orchestrator as subprocess
import subprocess
subprocess.run(['python', '-m', 'loquilex.cli.live_en_to_zh'])
```

**After (recommended):**
```python
# Use executor services directly
from loquilex.asr.stream import StreamingASR
from loquilex.mt.service import MTService
from loquilex.audio.capture import capture_stream

# Initialize services
asr = StreamingASR(stream_id="my-stream")
mt = MTService(dest_lang="zh")

# Orchestrate in your code
def on_audio_frame(frame):
    asr.process_audio_chunk(frame.data, on_partial, on_final)

def on_final(event):
    translation = await mt.translate(event.text)
    # Handle translation...

# Start capture
stop_fn = capture_stream(on_audio_frame)
```

## Architecture Principles

### JS-First Pattern

1. **JavaScript orchestrates** - Controls workflows, state, UI
2. **Python executes** - Handles ML inference, audio processing
3. **Clear boundaries** - Well-defined WebSocket/REST contracts

### Benefits

- **Separation of Concerns**: UI/orchestration vs ML/compute
- **Performance**: TypeScript throttles UI updates (2-10 Hz)
- **Type Safety**: End-to-end TypeScript interfaces
- **Scalability**: Independent scaling of frontend/backend

See: [JS-First Architecture Guide](./architecture/js-first.md)

## Timeline

- **Current (2024-11)**: Deprecation warnings added
- **Future (TBD)**: Legacy components will be removed in a breaking release
- **Migration Window**: At least 2 minor versions before removal

## Affected Tests

Tests using deprecated components will continue to work but may emit warnings:

```python
# Test will emit DeprecationWarning
def test_minimal_session_lifecycle():
    cfg = SessionConfig(streaming_mode=False)  # Legacy subprocess mode
    # ...
```

Suppress warnings in tests if needed:
```python
import warnings
with warnings.catch_warnings():
    warnings.simplefilter("ignore", DeprecationWarning)
    # ... test code using deprecated components
```

## Getting Help

- **Documentation**: See `docs/architecture/js-first.md`
- **Examples**: Check `tests/test_streaming_asr.py` for executor usage
- **Issues**: Report migration issues at https://github.com/Guffawaffle/LoquiLex/issues

## References

- Issue #60: https://github.com/Guffawaffle/LoquiLex/issues/60
- JS-First Architecture: [docs/architecture/js-first.md](./architecture/js-first.md)
- WebSocket API Contract: [docs/contracts/websocket.md](./contracts/websocket.md)
