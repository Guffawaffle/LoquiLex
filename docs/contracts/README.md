# API Contracts Reference

This directory contains the comprehensive API contracts for LoquiLex, defining the interfaces between JavaScript orchestration and Python execution layers.

## Contract Categories

### 🔌 WebSocket Contracts
Real-time bidirectional communication for live captioning and translation.

- **[WebSocket Protocol](./websocket.md)** - Message envelope format, session management
- **[ASR Streaming](./asr-streaming.md)** - Audio streaming and transcription events  
- **[Translation Events](./translation.md)** - Real-time translation message types
- **[Session Management](./session-management.md)** - Connection lifecycle and recovery

### 🌐 REST API Contracts
Configuration, control, and synchronous operations.

- **[Models API](./models-api.md)** - Model management and configuration
- **[Downloads API](./downloads-api.md)** - Model download orchestration
- **[Device Testing](./device-testing.md)** - Audio device validation endpoints
- **[Export Operations](./exports.md)** - Caption export and file generation

### 📊 Data Types
Shared type definitions used across all contracts.

- **[Core Types](./types/core.md)** - Base types and enums
- **[Audio Types](./types/audio.md)** - Audio processing data structures
- **[Progress Types](./types/progress.md)** - Progress tracking and throttling
- **[Error Types](./types/errors.md)** - Error handling and recovery

## Quick Reference

### WebSocket Message Envelope

All WebSocket messages use a consistent envelope format:

```typescript
interface WSEnvelope<TData = Record<string, unknown>> {
  v: number          // Schema version
  t: MessageType     // Message type (namespaced)
  sid?: string       // Session ID (server-issued)
  id?: string        // Message ID (server-unique)
  seq?: number       // Sequence number per session
  corr?: string      // Correlation ID for responses
  t_wall?: string    // ISO8601 timestamp
  t_mono_ns?: number // Monotonic nanoseconds since session start
  data: TData        // Type-specific payload
}
```

### Common Message Types

| Type | Direction | Purpose |
|------|-----------|---------|
| `session.hello` | Client → Server | Initial handshake |
| `session.welcome` | Server → Client | Connection established |
| `asr.partial` | Server → Client | Partial transcription |
| `asr.final` | Server → Client | Final transcription |
| `mt.final` | Server → Client | Translation result |
| `model.download.progress` | Server → Client | Download progress |

### REST Endpoints

| Method | Endpoint | Purpose |
|--------|----------|---------|
| `GET` | `/api/models` | List available models |
| `POST` | `/api/models/download` | Start model download |
| `GET` | `/api/device/test` | Test audio device |
| `POST` | `/api/exports` | Export captions |

## Versioning Strategy

### Schema Versioning

- **Envelope Version (`v`)**: Major protocol changes
- **Message Types (`t`)**: Namespace indicates feature area
- **Backward Compatibility**: Maintain support for previous envelope versions

### API Versioning

- **URL Versioning**: `/api/v1/`, `/api/v2/`
- **Header Versioning**: `Accept: application/vnd.loquilex.v1+json`
- **Graceful Degradation**: Older clients receive compatible responses

## Event Frequency Contracts

### UI Update Throttling

All real-time events are subject to frequency capping:

- **Minimum Frequency**: 2 Hz (500ms intervals)
- **Maximum Frequency**: 10 Hz (100ms intervals)  
- **Default Frequency**: 5 Hz (200ms intervals)
- **Enforcement**: Both client and server-side throttling

```typescript
// Client-side throttling
const throttledUpdate = createThrottler(updateProgress, { maxHz: 5 })

// Server-side rate limiting
class EventThrottler:
    def __init__(self, max_hz: int = 5):
        self.max_hz = max(2, min(10, max_hz))  # Clamp to 2-10 Hz
```

## Error Handling Contracts

### Standard Error Format

```typescript
interface APIError {
  code: string           // Machine-readable error code
  message: string        // Human-readable description
  details?: Record<string, unknown>  // Additional context
  timestamp: string      // ISO8601 error time
  correlation_id?: string // Request correlation ID
}
```

### WebSocket Error Events

```typescript
interface ErrorEventData {
  error: APIError
  recoverable: boolean   // Whether client should retry
  retry_after?: number   // Suggested retry delay (ms)
}
```

### HTTP Error Responses

```json
{
  "error": {
    "code": "MODEL_NOT_FOUND",
    "message": "The requested model 'large-v2' is not available",
    "details": {
      "available_models": ["base", "small", "medium"],
      "suggested_model": "medium"
    },
    "timestamp": "2024-09-17T12:00:00Z"
  }
}
```

## Connection Management

### WebSocket Lifecycle

1. **Connection**: Client initiates WebSocket connection
2. **Handshake**: `session.hello` → `session.welcome` exchange
3. **Active**: Bidirectional message exchange
4. **Heartbeat**: Periodic `session.heartbeat` messages
5. **Reconnection**: Automatic reconnection with session recovery
6. **Termination**: Clean shutdown with `session.goodbye`

### Session Recovery

```typescript
interface ResumeInfo {
  sid: string       // Previous session ID
  last_seq: number  // Last received sequence number
}

// Reconnection with resume
const hello: ClientHelloData = {
  agent: "loquilex-ui/0.3.0",
  resume: { sid: "sess_prev", last_seq: 42 }
}
```

## Authentication & Security

### WebSocket Authentication

- **Query Parameter**: `?token=<jwt_token>`
- **Header**: `Authorization: Bearer <jwt_token>`
- **Cookie**: `session=<session_id>` (for browser clients)

### REST API Authentication

```typescript
// Standard Bearer token
const response = await fetch('/api/models', {
  headers: {
    'Authorization': 'Bearer <token>',
    'Content-Type': 'application/json'
  }
})
```

## Testing Contracts

### Contract Testing

Each API contract includes:

- **JSON Schema**: Machine-readable contract definition
- **Example Payloads**: Sample requests and responses
- **Test Cases**: Automated contract validation
- **Mock Implementations**: Client and server mocks

### Example Test Structure

```typescript
describe('ASR Streaming Contract', () => {
  it('should send partial results within frequency limits', async () => {
    const results = await captureMessages(5000) // 5 second window
    const frequency = results.length / 5
    expect(frequency).toBeGreaterThanOrEqual(2) // Min 2 Hz
    expect(frequency).toBeLessThanOrEqual(10)   // Max 10 Hz
  })
})
```

## Contract Validation

### Runtime Validation

Both client and server validate messages against contracts:

```typescript
// Client-side validation
import { WSEnvelopeSchema } from './contracts/schemas'

const isValid = WSEnvelopeSchema.safeParse(receivedMessage)
if (!isValid.success) {
  logger.error('Invalid message received', isValid.error)
}
```

```python
# Server-side validation
from contracts.schemas import WSEnvelopeModel

try:
    envelope = WSEnvelopeModel.parse_obj(message)
except ValidationError as e:
    logger.error(f"Invalid message: {e}")
    return
```

### Contract Evolution

When contracts change:

1. **Add new fields** as optional first
2. **Deprecate old fields** with warnings
3. **Remove deprecated fields** in major version bumps
4. **Maintain backward compatibility** across minor versions

## Performance Contracts

### Response Time SLAs

| Operation | Target | Acceptable | Error Threshold |
|-----------|--------|------------|----------------|
| WebSocket Connect | < 100ms | < 500ms | > 2s |
| ASR Partial Result | < 50ms | < 200ms | > 1s |
| Translation | < 100ms | < 500ms | > 2s |
| Model Download Start | < 200ms | < 1s | > 5s |

### Throughput Guarantees

- **Audio Processing**: Real-time (1x speed minimum)
- **WebSocket Messages**: 2-10 Hz sustained
- **Concurrent Sessions**: 10+ per server instance
- **Model Download**: 50MB/s minimum on good connections

---

For detailed contract specifications, see the individual contract files linked above. Each contract includes comprehensive examples, validation rules, and implementation guidelines.