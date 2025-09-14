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

#### Connection
Connect to `/ws/{sid}` for real-time streaming events.

#### Event Schema

##### ASR Partial Event
Sent during live transcription when partial text is available.

```json
{
  "type": "asr.partial",
  "stream_id": "session_123",
  "segment_id": "seg001",
  "seq": 1,
  "text": "Hello world this is",
  "words": [
    {"w": "Hello", "t0": 0.0, "t1": 0.5, "conf": 0.95},
    {"w": "world", "t0": 0.5, "t1": 1.0, "conf": 0.92},
    {"w": "this", "t0": 1.0, "t1": 1.3, "conf": 0.88},
    {"w": "is", "t0": 1.3, "t1": 1.5, "conf": 0.91}
  ],
  "stable": false,
  "ts_monotonic": 1234567890.123
}
```

##### ASR Final Event
Sent when a complete segment is finalized.

```json
{
  "type": "asr.final",
  "stream_id": "session_123",
  "segment_id": "seg001",
  "seq": 2,
  "text": "Hello world this is a test.",
  "words": [
    {"w": "Hello", "t0": 0.0, "t1": 0.5, "conf": 0.95},
    {"w": "world", "t0": 0.5, "t1": 1.0, "conf": 0.92},
    {"w": "this", "t0": 1.0, "t1": 1.3, "conf": 0.88},
    {"w": "is", "t0": 1.3, "t1": 1.5, "conf": 0.91},
    {"w": "a", "t0": 1.5, "t1": 1.6, "conf": 0.89},
    {"w": "test", "t0": 1.6, "t1": 2.0, "conf": 0.94}
  ],
  "eou_reason": "punctuation",
  "segment_duration_ms": 2000.0,
  "ts_monotonic": 1234567892.456
}
```

##### Metrics Event
Periodic performance metrics broadcast.

```json
{
  "type": "asr_metrics.partial|asr_metrics.final",
  "stream_id": "session_123",
  "timestamp": 1234567890.123,
  "session_duration": 45.67,
  "text_length": 234,
  "word_count": 45,
  "seq": 12,
  "segment_id": "seg001"
}
```

##### MT Final Event
Sent when machine translation of a finalized ASR segment is complete.

```json
{
  "type": "mt.final",
  "stream_id": "session_123",
  "segment_id": "seg001",
  "seq": 3,
  "text": "你好，世界，这是一个测试。",
  "src_text": "Hello world this is a test.",
  "src_lang": "en",
  "tgt_lang": "zh-Hans",
  "provider": "ct2-nllb",
  "quality": "realtime",
  "ts_server": 1234567890.123,
  "ts_session": 12.345
}
```

##### MT Error Event
Sent when machine translation fails.

```json
{
  "type": "mt.error",
  "stream_id": "session_123",
  "segment_id": "seg001",
  "seq": 4,
  "error": "Translation model not available",
  "src_text": "Hello world",
  "ts_server": 1234567890.123,
  "ts_session": 12.345
}
```

## Client Example

Here's a minimal Python client example showing how to consume streaming events:

```python
import anyio
import websockets
import json
import requests

# Create a streaming session
response = requests.post("http://localhost:8000/sessions", json={
    "asr_model_id": "tiny.en",
    "streaming_mode": True,
    "mt_enabled": True,
    "dest_lang": "zh-Hans",
    "device": "cpu"
})
session_id = response.json()["session_id"]

async def consume_events():
    uri = f"ws://localhost:8000/ws/{session_id}"
    async with websockets.connect(uri) as websocket:
        while True:
            event = json.loads(await websocket.recv())
            if event["type"] == "asr.partial":
                print(f"Partial: {event['text']}")
            elif event["type"] == "asr.final":
                print(f"Final: {event['text']}")
            elif event["type"] == "mt.final":
                print(f"Translation: {event['text']} (from: {event['src_text']})")
            elif event["type"] == "mt.error":
                print(f"Translation error: {event['error']}")

# Run the consumer
asyncio.run(consume_events())

# Periodically check status
status = requests.get(f"http://localhost:8000/sessions/{session_id}/snapshot")
print(f"Status: {status.json()['status']}")

# Get metrics
metrics = requests.get(f"http://localhost:8000/sessions/{session_id}/metrics")
print(f"Metrics: {metrics.json()}")
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

WebSocket connections are resilient to temporary network issues and will automatically reconnect.