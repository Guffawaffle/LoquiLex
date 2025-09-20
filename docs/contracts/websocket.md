# WebSocket Protocol Contract

## Overview

LoquiLex uses WebSockets for real-time bidirectional communication between the JavaScript orchestration layer and Python execution services. All messages follow a consistent envelope format with version negotiation and error handling.

## Message Envelope

### Standard Envelope Format

```typescript
interface WSEnvelope<TData = Record<string, unknown>> {
  v: number          // Schema version (currently 1)
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

### Message Types

```typescript
type MessageType = 
  | 'session.hello'            // Client connection initiation
  | 'session.welcome'          // Server connection acknowledgment
  | 'session.heartbeat'        // Keep-alive ping/pong
  | 'session.ack'              // Generic acknowledgment
  | 'asr.partial'              // Partial transcription result
  | 'asr.final'                // Final transcription result
  | 'mt.final'                 // Translation result
  | 'status.update'            // System status change
  | 'model.download.started'   // Model download initiated
  | 'model.download.progress'  // Download progress update
  | 'model.download.completed' // Download completed
  | 'model.download.failed'    // Download failed
```

## Connection Lifecycle

### 1. Initial Handshake

**Client → Server**
```json
{
  "v": 1,
  "t": "session.hello",
  "data": {
    "client_version": "0.1.0",
    "supported_features": ["asr", "mt", "downloads"]
  }
}
```

**Server → Client**
```json
{
  "v": 1,
  "t": "session.welcome",
  "sid": "sess_1234567890abcdef",
  "data": {
    "server_version": "0.1.0",
    "session_id": "sess_1234567890abcdef",
    "supported_features": ["asr", "mt", "downloads"],
    "heartbeat_interval_ms": 30000
  }
}
```

### 2. Heartbeat Protocol

**Client ↔ Server (every 30 seconds)**
```json
{
  "v": 1,
  "t": "session.heartbeat",
  "sid": "sess_1234567890abcdef",
  "data": {
    "timestamp": "2024-01-15T10:30:00.000Z"
  }
}
```

### 3. Session Management

#### Connection Recovery
- Clients must reconnect with exponential backoff on disconnection
- Server maintains session state for 5 minutes after disconnection
- Clients should include last known `seq` number for message replay

#### Clean Shutdown
```json
{
  "v": 1,
  "t": "session.goodbye",
  "sid": "sess_1234567890abcdef",
  "data": {
    "reason": "client_shutdown"
  }
}
```

## Frequency Contracts

### Performance Limits
- **UI Updates**: 2-10 Hz maximum (throttled by client)
- **Heartbeat**: Every 30 seconds
- **Status Updates**: As needed, max 1 Hz
- **Progress Updates**: Max 2 Hz for downloads

### Throttling Strategy
```typescript
// Client-side throttling example
const throttleUpdates = throttle((update) => {
  updateUI(update)
}, 100) // 10 Hz max
```

## Error Handling

### Error Message Format
```json
{
  "v": 1,
  "t": "error",
  "sid": "sess_1234567890abcdef",
  "corr": "original_message_id",
  "data": {
    "code": "VALIDATION_ERROR",
    "message": "Invalid message format",
    "details": {
      "field": "data.model_id",
      "expected": "string",
      "received": "null"
    }
  }
}
```

### Standard Error Codes
- `VALIDATION_ERROR` - Message format validation failed
- `SESSION_EXPIRED` - Session ID no longer valid
- `RATE_LIMIT_EXCEEDED` - Too many messages sent
- `SERVICE_UNAVAILABLE` - Backend service not available
- `AUTHENTICATION_FAILED` - Invalid or missing credentials

## Security

### Authentication
WebSocket connections authenticate via:
- **Query Parameter**: `?token=<jwt_token>`
- **Header**: `Authorization: Bearer <jwt_token>`
- **Cookie**: `session=<session_id>` (browser clients)

### Content Security
- All messages validated against JSON schemas
- Rate limiting enforced per session
- Automatic session timeout after 1 hour of inactivity

## Testing

### Contract Validation
```typescript
import { WSEnvelopeSchema } from '../schemas'

// Validate incoming messages
const result = WSEnvelopeSchema.safeParse(receivedMessage)
if (!result.success) {
  logger.error('Invalid WebSocket message', result.error)
  return
}
```

### Mock WebSocket Server
```python
# Server-side contract testing
from contracts.schemas import WSEnvelopeModel

try:
    envelope = WSEnvelopeModel.parse_obj(message)
except ValidationError as e:
    logger.error(f"Invalid message: {e}")
    return
```

## Implementation Notes

### Client Responsibilities
- Implement exponential backoff for reconnection
- Throttle UI updates to prevent jank
- Validate all incoming messages
- Handle connection state changes gracefully

### Server Responsibilities  
- Maintain session state during temporary disconnections
- Enforce rate limits and message validation
- Provide consistent error responses
- Clean up resources on session termination

## Version Compatibility

### Schema Evolution
- **v1**: Current version with basic envelope format
- **Future versions**: Backward compatible additions only
- **Breaking changes**: Require major version increment

### Migration Strategy
```json
{
  "v": 2,
  "t": "session.hello",
  "data": {
    "client_version": "0.2.0",
    "min_server_version": "0.1.0"
  }
}
```

Server responds with highest mutually supported version.