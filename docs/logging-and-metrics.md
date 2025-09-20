# Structured Logging and Performance Metrics

LoquiLex implements comprehensive structured logging and performance metrics across all backend executors and UI orchestrator components. The system ensures offline safety, sensitive data redaction, and consistent monitoring capabilities.

## Overview

The logging system provides:

- **Structured JSON logging** with consistent format across all components
- **Automatic data redaction** for sensitive information (API keys, file paths, user data)
- **Performance metrics collection** with latency, throughput, counters, and gauges
- **Offline safety** - no external dependencies or network calls
- **Component isolation** with session correlation
- **Threshold monitoring** with warning and critical alerts

## Backend Components

### ASR Metrics (`loquilex.asr.metrics.ASRMetrics`)

Tracks speech recognition performance:

```python
from loquilex.asr.metrics import ASRMetrics

# Initialize with structured logging
metrics = ASRMetrics("stream_001")

# Events are automatically logged with performance tracking
metrics.on_partial_event({"text": "hello", "segment_id": "seg_1"})
metrics.on_final_event({"text": "hello world", "segment_id": "seg_1"})

# Get performance summary
summary = metrics.get_summary()
```

**Key Metrics:**
- Partial interval latency (target: <200ms p50, <300ms p95)
- Final latency from last partial (target: ≤800ms p95) 
- Events per second (partials/finals)
- End-of-utterance reason distribution

### MT Translator (`loquilex.mt.translator.Translator`)

Tracks machine translation performance:

```python
from loquilex.mt.translator import Translator

# Initialize with session-aware logging
translator = Translator(session_id="session_123")

# Translation timing is automatically tracked
result = translator.translate_en_to_zh("Hello world")
print(f"Translation took {result.duration_ms}ms")
```

**Key Metrics:**
- Translation latency (target: <1500ms warning, <3000ms critical)
- Model load time (target: <10s warning, <30s critical)
- Success/failure counters by method (NLLB/M2M)
- Fallback usage statistics

### API Supervisor (`loquilex.api.supervisor.SessionManager`)

Tracks session and WebSocket performance:

```python
# Session lifecycle is automatically logged with metrics
session_id = session_manager.start_session(config)
# Logs: session startup time, active session count

await session_manager.register_ws(session_id, websocket)  
# Logs: WebSocket connections, message latency
```

**Key Metrics:**
- Session startup time (target: <5s warning, <15s critical)
- Active sessions and WebSocket connections (gauges)
- WebSocket message latency (target: <100ms warning, <500ms critical)
- Session success/failure rates

## UI Orchestrator (TypeScript)

### Structured Logger (`loquilex.ui.web.src.orchestration.logging`)

Browser-compatible structured logging:

```typescript
import { createLogger, PerformanceMetrics } from '@/orchestration/logging'

// Create logger with local storage persistence
const logger = createLogger({
  component: 'websocket_client',
  session_id: 'ui_session_123',
  local_storage_key: 'loquilex_ui_logs'
})

// Performance metrics with WebSocket presets
const metrics = createWebSocketMetrics(logger)

// Log with automatic redaction
logger.info('WebSocket connected', {
  url: 'wss://localhost:8000/ws/session123?token=secret123',
  reconnect_count: 0
})

// Track performance
metrics.startTimer('websocket_message')
// ... send message ...
metrics.endTimer('websocket_message', { message_type: 'asr_partial' })
```

**Key Metrics:**
- WebSocket message latency (target: <100ms warning, <500ms critical)
- HTTP request latency (target: <1s warning, <5s critical)  
- UI render time (target: <16ms warning, <100ms critical)
- Connection health and retry statistics

## Configuration

### Environment Variables

Configure logging behavior via environment variables:

```bash
# Log file directory (optional)
export LX_LOG_DIR="/var/log/loquilex"

# WebSocket performance thresholds
export LX_WS_HB_INTERVAL_MS=10000      # Heartbeat interval
export LX_WS_HB_TIMEOUT_MS=30000       # Heartbeat timeout
export LX_WS_MAX_IN_FLIGHT=64          # Max concurrent messages
export LX_WS_MAX_MSG_BYTES=131072      # Max message size
```

### Programmatic Configuration

```python
from loquilex.logging import create_logger, PerformanceMetrics

# Custom logger with redaction
logger = create_logger(
    component="custom_component",
    session_id="session_456", 
    log_dir="/custom/log/dir"
)

# Custom metrics with thresholds
metrics = PerformanceMetrics(logger=logger)
metrics.set_threshold("custom_latency", warning=500.0, critical=2000.0)
```

## Data Redaction

Sensitive data is automatically redacted from logs:

### Redacted Information

- **API Keys/Tokens**: `token=abc123` → `token=[REDACTED]`
- **File Paths**: `/home/user/models/bert.bin` → `[REDACTED]/bert.bin`
- **Cache Directories**: `/.cache/huggingface/models/` → `[REDACTED]`
- **User Directories**: `/home/username/` → `[REDACTED]`
- **Sensitive Fields**: `password`, `secret`, `credential` → `[REDACTED]`

### Custom Redaction

```python
from loquilex.logging import DataRedactor

# Add custom patterns
redactor = DataRedactor()
redactor.add_pattern(r'custom_secret_\w+')
redactor.add_sensitive_field('internal_token')
```

## Log Format

All logs use consistent JSON structure:

```json
{
  "timestamp": 1758119167.531,
  "iso_timestamp": "2025-09-17T14:26:07Z", 
  "level": "info",
  "component": "asr_metrics",
  "session_id": "stream_001",
  "session_time": 0.0014,
  "message": "ASR metrics initialized",
  "stream_id": "stream_001"
}
```

## Performance Targets

### ASR Processing
- **Partial intervals**: <200ms p50, <300ms p95
- **Final latency**: ≤800ms p95
- **Throughput**: >5 partials/second

### Machine Translation  
- **Translation latency**: <1500ms warning, <3000ms critical
- **Model load time**: <10s warning, <30s critical

### WebSocket Communication
- **Message latency**: <100ms warning, <500ms critical
- **Connection time**: <2s warning, <10s critical

### UI Performance
- **Render time**: <16ms (60fps) warning, <100ms critical
- **HTTP requests**: <1s warning, <5s critical

## Monitoring Integration

The structured logs and metrics can be integrated with monitoring systems:

### Log Aggregation
```bash
# Forward logs to centralized system
tail -f /var/log/loquilex/*.jsonl | logger -t loquilex

# Parse with jq for analysis
cat session.jsonl | jq 'select(.level == "error")' 
```

### Metrics Export
```python
# Export metrics for monitoring dashboard
metrics_summary = metrics.get_all_metrics()
# Send to Prometheus, DataDog, etc.
```

## Troubleshooting

### High Latency Alerts

Monitor log files for threshold violations:

```bash
# Find critical performance issues
grep '"threshold_type":"critical"' *.jsonl

# ASR performance problems
grep '"partial_p95_target":false' *.jsonl
```

### Session Debugging

Use session correlation for debugging:

```bash
# Track session lifecycle
grep '"session_id":"session_123"' *.jsonl | jq '.message'
```

### WebSocket Issues

Monitor connection health:

```typescript
// Get WebSocket metrics
const wsMetrics = metrics.getStats('websocket_message_latency')
if (wsMetrics && wsMetrics.p95 > 500) {
  logger.warning('WebSocket performance degraded', { p95: wsMetrics.p95 })
}
```

This comprehensive logging and metrics system provides full observability into LoquiLex performance while maintaining offline safety and data privacy.