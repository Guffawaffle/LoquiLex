# LoquiLex API Documentation

This document describes the REST API endpoints and WebSocket event schema for LoquiLex, a local-first live captioning and translation system.

## Endpoints

### Sessions

#### POST /sessions
Create a new ASR session.

**Request Body:**
```json
{
  "asr_model_id": "tiny.en",
  "streaming_mode": false,
  "device": "cpu",
  "mt_enabled": false,
  "mt_model_id": null,
  "dest_lang": "zh"
}
```

**Response:**
```json
{
  "session_id": "abc123"
}
```

#### DELETE /sessions/{sid}
Stop and delete a session.

**Response:**
```json
{
  "ok": true
}
```

#### GET /sessions/{sid}/snapshot
Get the current status and configuration of a session.

**Response:**
```json
{
  "status": "running|stopped",
  "cfg": {
    "name": "session_name",
    "asr_model_id": "tiny.en",
    "device": "cpu",
    "streaming_mode": true
  },
  "last_event": {
    "type": "asr.partial|asr.final",
    "text": "Hello world",
    "words": [
      {"w": "Hello", "t0": 0.0, "t1": 0.5, "conf": 0.95},
      {"w": "world", "t0": 0.5, "t1": 1.0, "conf": 0.92}
    ],
    "seq": 1,
    "segment_id": "seg001"
  }
}
```

#### GET /sessions/{sid}/metrics
Get performance metrics for a session.

**Response:**
```json
{
  "session_duration": 45.67,
  "total_segments": 12,
  "avg_segment_duration": 3.81,
  "total_text_length": 234,
  "avg_confidence": 0.87,
  "processing_rate": 2.34
}
```

### WebSocket Events

**New in v1:** LoquiLex now uses a **versioned envelope protocol** for all WebSocket messages with heartbeats, acknowledgements, and resume functionality.

#### Connection
Connect to `/events/{sid}` for real-time streaming events with the new envelope protocol.

#### Envelope Schema (v1)

All WebSocket messages use a shared envelope structure:

```json
{
  "v": 1,                        // Schema version
  "t": "asr.partial",            // Message type (namespaced)
  "sid": "sess_8Gm6...",         // Session ID (server-issued)
  "id": "msg_a1b2c3",            // Message ID (server-unique)
  "seq": 42,                     // Sequence number per session
  "corr": "msg_prev",            // Optional correlation ID
  "t_wall": "2025-09-14T18:03:26.512Z",  // ISO8601 timestamp
  "t_mono_ms": 1234567,          // Milliseconds since session start
  "data": { /* type-specific payload */ }
}
```

#### Control Messages

##### Client Hello
Sent by client after connection to announce capabilities:

```json
{
  "v": 1,
  "t": "client.hello",
  "data": {
    "agent": "loquilex-ui/0.3.0",
    "accept": ["asr.partial", "asr.final", "mt.final"],
    "ack_mode": "cumulative",      // "cumulative" | "per-message"
    "max_in_flight": 32,           // Sliding window size
    "resume": {                    // Optional resume info
      "sid": "sess_8Gm6...",
      "last_seq": 41
    }
  }
}
```

##### Server Welcome  
Sent by server after client connection:

```json
{
  "v": 1,
  "t": "server.welcome", 
  "sid": "sess_8Gm6...",
  "seq": 0,
  "data": {
    "hb": {
      "interval_ms": 10000,        // Heartbeat interval
      "timeout_ms": 30000          // Heartbeat timeout
    },
    "resume_window": {
      "seconds": 300,              // Resume window duration
      "token": "rTok_xxx"          // Resume token (optional)
    },
    "limits": {
      "max_in_flight": 64,         // Server max sliding window
      "max_msg_bytes": 131072      // Max message size
    }
  }
}
```

##### Heartbeats
Server and client exchange heartbeats to detect liveness:

```json
{
  "v": 1,
  "t": "server.hb",
  "sid": "sess_8Gm6...",
  "seq": 7,
  "data": {
    "ts": "2025-09-14T18:03:30.000Z",
    "q_out": 0,                    // Server outbound queue depth
    "q_in": 0,                     // Server inbound queue depth  
    "latency_ms_est": 48           // Estimated latency
  }
}
```

##### Acknowledgements
Client acknowledges received messages for flow control:

```json
{
  "v": 1,
  "t": "client.ack",
  "sid": "sess_8Gm6...",
  "data": {
    "ack_seq": 42                  // Cumulative ack up to sequence 42
  }
}
```

#### Domain Events

Domain events use the same envelope with type-specific payloads:

##### ASR Partial Event
Sent during live transcription when partial text is available:

```json
{
  "v": 1,
  "t": "asr.partial",
  "sid": "sess_123",
  "seq": 1,
  "t_wall": "2025-09-14T18:03:26.512Z",
  "t_mono_ms": 1234,
  "data": {
    "text": "Hello world this is",
    "segment_id": "seg001",
    "final": false
  }
}
```

##### ASR Final Event
Sent when a complete segment is finalized:

```json
{
  "v": 1,
  "t": "asr.final", 
  "sid": "sess_123",
  "seq": 2,
  "t_wall": "2025-09-14T18:03:28.512Z",
  "t_mono_ms": 3456,
  "data": {
    "text": "Hello world this is a test.",
    "segment_id": "seg001",
    "start_ms": 0,
    "end_ms": 2000
  }
}
```

##### MT Final Event
Sent when machine translation of a finalized ASR segment is complete:

```json
{
  "v": 1,
  "t": "mt.final",
  "sid": "sess_123", 
  "seq": 3,
  "corr": "msg_asr_final",           // Links to source ASR message
  "t_wall": "2025-09-14T18:03:29.512Z",
  "t_mono_ms": 4567,
  "data": {
    "text": "你好，世界，这是一个测试。",
    "src": "en",
    "tgt": "zh-Hans"
  }
}
```

##### Status Event
Sent for session status updates:

```json
{
  "v": 1,
  "t": "status",
  "sid": "sess_123",
  "seq": 4, 
  "t_wall": "2025-09-14T18:03:30.512Z",
  "t_mono_ms": 5678,
  "data": {
    "stage": "processing",
    "detail": "Audio analysis in progress"
  }
}
```

#### Flow Control & Reliability

The new protocol includes several reliability features:

- **Sliding Window**: Server respects `max_in_flight` limit to prevent overwhelming client
- **Acknowledgements**: Client sends `client.ack` messages; server maintains replay buffer
- **Resume/Reconnect**: Client can reconnect and replay missed messages within window
- **Heartbeats**: Bi-directional liveness detection with configurable intervals
- **At-least-once delivery**: Messages may be delivered multiple times; client should handle duplicates

## Client Example

Here's a Python client example using the new envelope protocol:

```python
import asyncio
import json
import requests
import websockets
from datetime import datetime

# Create a streaming session
response = requests.post("http://localhost:8000/sessions", json={
    "asr_model_id": "tiny.en",
    "streaming_mode": True,
    "mt_enabled": True,
    "dest_lang": "zh-Hans",
    "device": "cpu"
})
session_id = response.json()["session_id"]

class LoquiLexClient:
    def __init__(self, session_id: str):
        self.session_id = session_id
        self.last_ack_seq = 0
        self.websocket = None
        
    async def connect(self):
        """Connect and handle the envelope protocol."""
        uri = f"ws://localhost:8000/events/{self.session_id}"
        self.websocket = await websockets.connect(uri)
        
        # Wait for welcome message
        welcome_raw = await self.websocket.recv()
        welcome = json.loads(welcome_raw)
        print(f"Connected! Welcome: {welcome['t']}")
        
        # Send client hello
        hello = {
            "v": 1,
            "t": "client.hello",
            "data": {
                "agent": "example-client/1.0",
                "accept": ["asr.partial", "asr.final", "mt.final", "status"],
                "ack_mode": "cumulative",
                "max_in_flight": 16
            }
        }
        await self.websocket.send(json.dumps(hello))
        
        # Acknowledge welcome
        await self.send_ack(welcome["seq"])
        
    async def send_ack(self, seq: int):
        """Send acknowledgement for received messages."""
        if seq > self.last_ack_seq:
            ack = {
                "v": 1,
                "t": "client.ack", 
                "sid": self.session_id,
                "data": {"ack_seq": seq}
            }
            await self.websocket.send(json.dumps(ack))
            self.last_ack_seq = seq
        
    async def listen(self):
        """Listen for messages and handle them."""
        while True:
            try:
                message_raw = await self.websocket.recv()
                envelope = json.loads(message_raw)
                
                # Handle different message types
                if envelope["t"] == "asr.partial":
                    print(f"Partial: {envelope['data']['text']}")
                elif envelope["t"] == "asr.final":
                    print(f"Final: {envelope['data']['text']}")
                elif envelope["t"] == "mt.final":
                    print(f"Translation: {envelope['data']['text']}")
                elif envelope["t"] == "status":
                    print(f"Status: {envelope['data']['stage']}")
                elif envelope["t"] == "server.hb":
                    print("❤️ Heartbeat received")
                    
                # Acknowledge non-control messages
                if envelope["t"] not in ["server.hb", "server.welcome", "server.ack"]:
                    await self.send_ack(envelope["seq"])
                    
            except websockets.exceptions.ConnectionClosed:
                print("Connection closed")
                break

async def main():
    client = LoquiLexClient(session_id)
    await client.connect()
    await client.listen()

# Run the client
asyncio.run(main())
```

#### Configuration via Environment Variables

WebSocket behavior can be configured via environment variables:

- `LX_WS_HB_INTERVAL_MS`: Heartbeat interval in milliseconds (default: 10000)
- `LX_WS_HB_TIMEOUT_MS`: Heartbeat timeout in milliseconds (default: 30000)  
- `LX_WS_MAX_IN_FLIGHT`: Maximum sliding window size (default: 64)
- `LX_WS_MAX_MSG_BYTES`: Maximum message size in bytes (default: 131072)
```

## Offline-First Design

LoquiLex is designed to work entirely offline:
- All ML models are downloaded once and cached locally
- No external API calls during normal operation
- Tests use fake implementations to avoid network dependencies
- Configuration uses environment variables and local files only

## Error Handling

All endpoints return appropriate HTTP status codes:
- `200`: Success
- `404`: Session not found
- `500`: Internal server error (generic message, no exception details leaked)

WebSocket connections use the new envelope protocol with resilience features:
- Automatic reconnection with message replay within the resume window
- Flow control to prevent client overload
- Heartbeat monitoring for connection health
- At-least-once delivery with client-side deduplication