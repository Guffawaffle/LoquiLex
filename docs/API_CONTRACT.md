# LoquiLex API Contract

**Version:** 0.1.0  
**Protocol:** REST HTTP + WebSocket  
**Base URL:** `http://localhost:8000` (configurable via `LX_API_PORT`)

This document defines the complete API contract between the LoquiLex backend and frontend applications (LoquiLex-UI web and native apps), enabling independent development and integration.

## Table of Contents

- [Overview](#overview)
- [REST API Endpoints](#rest-api-endpoints)
- [WebSocket Protocol](#websocket-protocol)
- [Authentication & Security](#authentication--security)
- [Configuration](#configuration)
- [Deployment](#deployment)
- [Versioning & Compatibility](#versioning--compatibility)
- [Error Handling](#error-handling)
- [Testing](#testing)

---

## Overview

LoquiLex exposes two primary interfaces:

1. **REST API**: Synchronous operations for configuration, session management, model management, and system control
2. **WebSocket API**: Real-time bidirectional communication for live transcription, translation, and event streaming

### Architecture

- **Backend**: FastAPI server (Python 3.10+)
- **Frontend**: React/Electron applications (TypeScript)
- **Communication**: HTTP REST + WebSocket
- **Data Format**: JSON

### Key Features

- ✅ **Session-based**: Multi-session support with independent audio streams
- ✅ **Real-time**: Sub-second latency for transcription and translation
- ✅ **Resumable**: WebSocket reconnection with state recovery
- ✅ **Offline-first**: Works without internet connectivity
- ✅ **CORS-enabled**: Cross-origin support in development mode

---

## REST API Endpoints

### Interactive Documentation

FastAPI automatically generates interactive API documentation:

- **Swagger UI**: `http://localhost:8000/docs`
- **ReDoc**: `http://localhost:8000/redoc`
- **OpenAPI Schema**: `http://localhost:8000/openapi.json`

### Health & Status

#### `GET /healthz`

Check server health and readiness.

**Response:**
```json
{
  "status": "ok",
  "timestamp": 1698765432.123
}
```

**Status Codes:**
- `200 OK`: Server is healthy

#### `GET /api/health`

Alternative health check endpoint.

**Response:**
```json
{
  "status": "ok"
}
```

**Status Codes:**
- `200 OK`: Server is healthy

#### `HEAD /api/health`

Lightweight health check (no response body).

**Status Codes:**
- `200 OK`: Server is healthy

---

### Session Management

Sessions represent independent audio capture and processing pipelines.

#### `POST /sessions`

Create a new captioning/translation session.

**Request Body:**
```json
{
  "name": "My Session",
  "asr_model_id": "small.en",
  "mt_enabled": true,
  "mt_model_id": "facebook/nllb-200-distilled-600M",
  "dest_lang": "zho_Hans",
  "device": "auto",
  "vad": true,
  "beams": 1,
  "pause_flush_sec": 0.7,
  "segment_max_sec": 7.0,
  "partial_word_cap": 10,
  "save_audio": "off",
  "streaming_mode": false
}
```

**Parameters:**
- `name` (optional): Human-readable session name
- `asr_model_id` (required): ASR model identifier (e.g., `small.en`, `base`, `medium`)
- `mt_enabled` (optional, default `false`): Enable machine translation
- `mt_model_id` (optional): MT model identifier (required if `mt_enabled=true`)
- `dest_lang` (optional, default `zho_Hans`): Target language code
- `device` (optional, default `auto`): Device selection (`auto`, `cuda`, `cpu`)
- `vad` (optional, default `true`): Enable voice activity detection
- `beams` (optional, default `1`): Beam search width
- `pause_flush_sec` (optional, default `0.7`): Pause duration before flushing segment
- `segment_max_sec` (optional, default `7.0`): Maximum segment duration
- `partial_word_cap` (optional, default `10`): Maximum words in partial results
- `save_audio` (optional, default `off`): Audio save format (`off`, `wav`, `flac`)
- `streaming_mode` (optional, default `false`): Enable streaming ASR pipeline

**Response:**
```json
{
  "session_id": "sess_abc123def456"
}
```

**Status Codes:**
- `200 OK`: Session created successfully
- `400 Bad Request`: Invalid parameters
- `409 Conflict`: Resource conflict (e.g., GPU busy)

**Error Response:**
```json
{
  "detail": {
    "error": "GPU busy with another session",
    "requested_device": "cuda"
  }
}
```

#### `DELETE /sessions/{sid}`

Stop and destroy a session.

**Path Parameters:**
- `sid`: Session ID

**Response:**
```json
{
  "stopped": true
}
```

**Status Codes:**
- `200 OK`: Session stopped
- `404 Not Found`: Session does not exist

#### `POST /sessions/{sid}/pause`

Pause audio capture for a session.

**Response:**
```json
{
  "ok": true
}
```

**Status Codes:**
- `200 OK`: Session paused
- `404 Not Found`: Session does not exist

#### `POST /sessions/{sid}/resume`

Resume audio capture for a paused session.

**Response:**
```json
{
  "ok": true
}
```

**Status Codes:**
- `200 OK`: Session resumed
- `404 Not Found`: Session does not exist

#### `POST /sessions/{sid}/finalize`

Finalize and flush any pending transcription for a session.

**Response:**
```json
{
  "ok": true
}
```

**Status Codes:**
- `200 OK`: Session finalized
- `404 Not Found`: Session does not exist

#### `GET /sessions/{sid}/snapshot`

Get complete session state snapshot for reconnection or status display.

**Response:**
```json
{
  "sid": "sess_abc123",
  "cfg": {
    "name": "My Session",
    "asr_model_id": "small.en",
    "mt_enabled": true,
    "device": "cuda"
  },
  "status": "running",
  "asr": {
    "finalized_transcript": [...],
    "active_partials": [...]
  },
  "mt": {
    "status": "active",
    "pending_count": 2
  },
  "session_storage": {
    "commit_count": 42,
    "size_bytes": 102400
  }
}
```

**Status Codes:**
- `200 OK`: Snapshot retrieved
- `404 Not Found`: Session does not exist

#### `GET /sessions/{sid}/metrics`

Get performance metrics for a streaming session.

**Response:**
```json
{
  "audio_processing_ms": 45.2,
  "asr_latency_ms": 123.4,
  "mt_latency_ms": 89.1,
  "queue_depth": 3
}
```

**Status Codes:**
- `200 OK`: Metrics retrieved
- `400 Bad Request`: Session does not support metrics (non-streaming)
- `404 Not Found`: Session does not exist
- `503 Service Unavailable`: Metrics not available

#### `GET /sessions/{sid}/asr/snapshot`

Get ASR-specific snapshot (streaming sessions only).

**Response:**
```json
{
  "finalized_transcript": [
    {
      "text": "Hello world",
      "segment_id": "seg_001",
      "start_ms": 0,
      "end_ms": 1200
    }
  ],
  "active_partials": [
    {
      "text": "This is partial",
      "segment_id": "seg_002"
    }
  ]
}
```

**Status Codes:**
- `200 OK`: Snapshot retrieved
- `400 Bad Request`: Not a streaming session
- `404 Not Found`: Session does not exist
- `503 Service Unavailable`: Snapshot not available

#### `POST /sessions/selftest`

Run device and ASR model self-test.

**Request Body:**
```json
{
  "asr_model_id": "small.en",
  "device": "auto",
  "seconds": 1.5
}
```

**Response:**
```json
{
  "ok": true,
  "asr_load_ms": 1234,
  "rms_avg": 0.042,
  "message": "ok",
  "effective_asr_model": "small.en",
  "effective_device": "cuda",
  "effective_compute": "float16",
  "sample_rate": 16000
}
```

**Status Codes:**
- `200 OK`: Self-test completed

---

### Model Management

#### `GET /models/asr`

List available ASR (Automatic Speech Recognition) models.

**Response:**
```json
[
  {
    "id": "small.en",
    "name": "Whisper Small (English)",
    "size_mb": 461,
    "languages": ["en"],
    "available": true
  },
  {
    "id": "base",
    "name": "Whisper Base (Multilingual)",
    "size_mb": 142,
    "languages": ["*"],
    "available": true
  }
]
```

**Status Codes:**
- `200 OK`: Model list retrieved

#### `GET /models/mt`

List available MT (Machine Translation) models.

**Response:**
```json
[
  {
    "id": "facebook/nllb-200-distilled-600M",
    "name": "NLLB-200 Distilled 600M",
    "size_mb": 2400,
    "available": true
  }
]
```

**Status Codes:**
- `200 OK`: Model list retrieved

#### `GET /languages/mt/{model_id}`

Get supported target languages for an MT model.

**Path Parameters:**
- `model_id`: MT model identifier (URL-encoded)

**Response:**
```json
{
  "model_id": "facebook/nllb-200-distilled-600M",
  "languages": [
    {
      "code": "zho_Hans",
      "name": "Chinese (Simplified)"
    },
    {
      "code": "spa_Latn",
      "name": "Spanish"
    }
  ]
}
```

**Status Codes:**
- `200 OK`: Language list retrieved

#### `POST /models/download`

Start model download.

**Request Body:**
```json
{
  "repo_id": "facebook/nllb-200-distilled-600M",
  "type": "mt"
}
```

**Parameters:**
- `repo_id` (required): HuggingFace repository ID
- `type` (required): Model type (`asr`, `mt`, `other`)

**Response:**
```json
{
  "job_id": "dljob_xyz789",
  "status": "started"
}
```

**Status Codes:**
- `200 OK`: Download job started

**Note:** Progress is streamed via WebSocket on the `_download` channel.

#### `DELETE /models/download/{job_id}`

Cancel a download job.

**Path Parameters:**
- `job_id`: Download job ID

**Response:**
```json
{
  "cancelled": true
}
```

**Status Codes:**
- `200 OK`: Job cancelled (or already completed)

#### `GET /models/downloads`

Get status of all download jobs.

**Response:**
```json
{
  "jobs": [
    {
      "job_id": "dljob_xyz789",
      "repo_id": "facebook/nllb-200-distilled-600M",
      "type": "mt",
      "status": "downloading",
      "progress": 65,
      "created_at": "2024-11-01T03:00:00Z",
      "started_at": "2024-11-01T03:00:05Z",
      "completed_at": null,
      "error_message": null
    }
  ],
  "active_count": 1,
  "queued_count": 0,
  "completed_count": 3,
  "total_count": 4
}
```

**Status Codes:**
- `200 OK`: Job list retrieved

#### `POST /models/downloads/bandwidth`

Set download bandwidth limit.

**Request Body:**
```json
{
  "limit_mbps": 10
}
```

**Parameters:**
- `limit_mbps` (required): Bandwidth limit in MB/s (0 = unlimited)

**Response:**
```json
{
  "limit_mbps": 10,
  "active": true
}
```

**Status Codes:**
- `200 OK`: Bandwidth limit set

#### `GET /models/downloads/bandwidth`

Get current bandwidth limit.

**Response:**
```json
{
  "limit_mbps": 10,
  "active": true
}
```

**Status Codes:**
- `200 OK`: Bandwidth info retrieved

#### `POST /models/downloads/pause-all`

Pause all active downloads.

**Response:**
```json
{
  "paused_count": 2
}
```

**Status Codes:**
- `200 OK`: Downloads paused

#### `POST /models/downloads/resume-all`

Resume all paused downloads.

**Response:**
```json
{
  "resumed_count": 2
}
```

**Status Codes:**
- `200 OK`: Downloads resumed

---

### Storage & File Management

#### `GET /storage/info`

Get storage information for a path.

**Query Parameters:**
- `path` (optional): Path to check (default: output directory)

**Response:**
```json
{
  "path": "/home/user/loquilex/out",
  "total_bytes": 1000000000000,
  "free_bytes": 500000000000,
  "used_bytes": 500000000000,
  "percent_used": 50.0,
  "writable": true
}
```

**Status Codes:**
- `200 OK`: Storage info retrieved
- `400 Bad Request`: Invalid path

#### `POST /storage/base-directory`

Set and validate a new base directory for storage.

**Request Body:**
```json
{
  "path": "/absolute/path/to/storage"
}
```

**Response:**
```json
{
  "path": "/absolute/path/to/storage",
  "valid": true,
  "message": "Directory is valid and writable"
}
```

**Status Codes:**
- `200 OK`: Directory validated (check `valid` field)

#### `GET /sessions/{sid}/storage/stats`

Get storage statistics for a session.

**Response:**
```json
{
  "commit_count": 42,
  "size_bytes": 102400,
  "oldest_commit_timestamp": 1698765432.0
}
```

**Status Codes:**
- `200 OK`: Stats retrieved
- `400 Bad Request`: Session does not support storage
- `404 Not Found`: Session does not exist
- `503 Service Unavailable`: Storage not available

#### `GET /sessions/{sid}/storage/commits`

Get session commits (transcript/translation history).

**Query Parameters:**
- `limit` (optional): Maximum number of commits to return
- `commit_type` (optional): Filter by commit type (`transcript`, `translation`, `status`)
- `since_timestamp` (optional): Only return commits after this timestamp

**Response:**
```json
{
  "session_id": "sess_abc123",
  "commits": [
    {
      "id": "commit_001",
      "timestamp": 1698765432.0,
      "seq": 1,
      "type": "transcript",
      "data": {
        "text": "Hello world",
        "segment_id": "seg_001"
      }
    }
  ],
  "total_returned": 1
}
```

**Status Codes:**
- `200 OK`: Commits retrieved
- `400 Bad Request`: Session does not support storage
- `404 Not Found`: Session does not exist

---

### Hardware & System

#### `GET /hardware/snapshot`

Get hardware capabilities snapshot.

**Response:**
```json
{
  "cpu": {
    "name": "Intel Core i7-9700K",
    "cores_physical": 8,
    "cores_logical": 8,
    "frequency_mhz": 3600.0,
    "usage_percent": 25.3,
    "meets_threshold": true,
    "warnings": []
  },
  "gpus": [
    {
      "name": "NVIDIA GeForce RTX 3080",
      "memory_total_mb": 10240,
      "memory_free_mb": 8192,
      "memory_used_mb": 2048,
      "temperature_c": 65,
      "utilization_percent": 30,
      "cuda_available": true,
      "meets_threshold": true,
      "warnings": []
    }
  ],
  "audio_devices": [
    {
      "index": 0,
      "name": "Built-in Microphone",
      "channels": 2,
      "sample_rate": 48000
    }
  ],
  "memory_total_gb": 32.0,
  "memory_available_gb": 16.5,
  "platform_info": {
    "system": "Linux",
    "release": "5.15.0",
    "machine": "x86_64"
  },
  "overall_status": "optimal",
  "overall_score": 95,
  "warnings": []
}
```

**Status Codes:**
- `200 OK`: Snapshot retrieved

**Note:** Results are cached for 10 seconds.

---

### Configuration & Profiles

#### `GET /settings/defaults`

Get default model settings.

**Response:**
```json
{
  "asr_model_id": "small.en",
  "asr_device": "auto",
  "asr_compute_type": "float16",
  "mt_model_id": null,
  "mt_device": "auto",
  "mt_compute_type": "float16",
  "tts_model_id": null,
  "tts_device": "auto"
}
```

**Status Codes:**
- `200 OK`: Defaults retrieved

#### `POST /settings/defaults`

Update default model settings.

**Request Body:**
```json
{
  "asr_model_id": "base.en",
  "asr_device": "cuda"
}
```

**Response:**
```json
{
  "asr_model_id": "base.en",
  "asr_device": "cuda",
  "asr_compute_type": "float16",
  "mt_model_id": null,
  "mt_device": "auto",
  "mt_compute_type": "float16",
  "tts_model_id": null,
  "tts_device": "auto"
}
```

**Status Codes:**
- `200 OK`: Defaults updated

#### `GET /profiles`

List saved session profiles.

**Response:**
```json
["default", "presentation", "lecture"]
```

**Status Codes:**
- `200 OK`: Profile list retrieved

#### `GET /profiles/{name}`

Get profile configuration.

**Path Parameters:**
- `name`: Profile name

**Response:**
```json
{
  "name": "presentation",
  "asr_model_id": "small.en",
  "mt_enabled": true,
  "dest_lang": "zho_Hans",
  "beams": 5
}
```

**Status Codes:**
- `200 OK`: Profile retrieved
- `400 Bad Request`: Invalid profile name
- `404 Not Found`: Profile does not exist

#### `POST /profiles/{name}`

Save or update profile configuration.

**Path Parameters:**
- `name`: Profile name

**Request Body:**
```json
{
  "name": "presentation",
  "asr_model_id": "small.en",
  "mt_enabled": true,
  "dest_lang": "zho_Hans"
}
```

**Response:**
```json
{
  "ok": true,
  "path": "/home/user/loquilex/out/profiles/presentation.json"
}
```

**Status Codes:**
- `200 OK`: Profile saved
- `400 Bad Request`: Invalid profile name or data

#### `DELETE /profiles/{name}`

Delete a profile.

**Path Parameters:**
- `name`: Profile name

**Response:**
```json
{
  "ok": true
}
```

**Status Codes:**
- `200 OK`: Profile deleted (or did not exist)
- `400 Bad Request`: Invalid profile name

---

### Administration

#### `POST /admin/cache/clear`

Clear in-process caches (requires admin token).

**Headers:**
```
Authorization: Bearer <admin_token>
```

**Response:**
```json
{
  "ok": true,
  "cleared": true,
  "prior_cache_present": true
}
```

**Status Codes:**
- `200 OK`: Cache cleared
- `403 Forbidden`: Missing or invalid admin token

---

## WebSocket Protocol

### Connection URL

```
ws://localhost:8000/ws/{session_id}
```

**Path Parameters:**
- `session_id`: Session ID obtained from `POST /sessions`

**Note:** In development mode with `LX_WS_ALLOW_EVENTS_ALIAS=1`, the legacy path `/events/{session_id}` is also supported.

### Connection Lifecycle

1. **Client → Server**: WebSocket connection established
2. **Server → Client**: `SERVER_WELCOME` message with configuration
3. **Client → Server**: Optional `CLIENT_HELLO` with preferences
4. **Server ↔ Client**: Bidirectional message exchange
5. **Server → Client**: Periodic `SERVER_HB` heartbeat messages
6. **Client → Server**: Optional `CLIENT_ACK` acknowledgements
7. **Connection closed**: Automatic cleanup after timeout or explicit disconnect

### Message Envelope Format

All WebSocket messages use a standardized envelope:

```typescript
interface WSEnvelope<TData = Record<string, unknown>> {
  v: number          // Schema version (currently 1)
  t: MessageType     // Message type (namespaced)
  sid?: string       // Session ID (server-issued)
  id?: string        // Message ID (server-unique)
  seq?: number       // Sequence number per session (for ordering/ack)
  corr?: string      // Correlation ID for request/response linking
  t_wall?: string    // ISO8601 wall-clock timestamp
  t_mono_ns?: number // Monotonic nanoseconds since session start
  data: TData        // Type-specific payload
}
```

### Message Types

#### Control Messages

| Type | Direction | Description |
|------|-----------|-------------|
| `client.hello` | Client → Server | Initial handshake with capabilities |
| `server.welcome` | Server → Client | Connection established, server config |
| `server.error` | Server → Client | Error notification |
| `server.ack` | Server → Client | Generic acknowledgement response |
| `client.hb` | Client → Server | Client heartbeat |
| `server.hb` | Server → Client | Server heartbeat with metrics |
| `client.ack` | Client → Server | Acknowledge received messages |
| `client.flow` | Client → Server | Flow control update |

#### Domain Event Messages

| Type | Direction | Description |
|------|-----------|-------------|
| `asr.partial` | Server → Client | Partial transcription result |
| `asr.final` | Server → Client | Final transcription segment |
| `mt.partial` | Server → Client | Partial translation result |
| `mt.final` | Server → Client | Final translation segment |
| `status` | Server → Client | Status update |

#### Resume/Recovery Messages

| Type | Direction | Description |
|------|-----------|-------------|
| `session.resume` | Client → Server | Resume session after reconnect |
| `session.snapshot` | Server → Client | Session state for rehydration |
| `session.new` | Server → Client | Resume failed, fresh start required |
| `session.ack` | Server → Client | Session handshake complete |
| `system.heartbeat` | Server → Client | System metrics heartbeat |
| `system.metrics` | Server → Client | Detailed system telemetry |
| `queue.drop` | Server → Client | Queue overflow notification |

### Example Messages

#### Server Welcome

```json
{
  "v": 1,
  "t": "server.welcome",
  "sid": "sess_abc123",
  "id": "msg_xyz789",
  "seq": 0,
  "t_wall": "2024-11-01T03:00:00.000Z",
  "data": {
    "hb": {
      "interval_ms": 5000,
      "timeout_ms": 15000
    },
    "resume_window": {
      "seconds": 10
    },
    "limits": {
      "max_in_flight": 64,
      "max_msg_bytes": 131072
    }
  }
}
```

#### Client Hello

```json
{
  "v": 1,
  "t": "client.hello",
  "data": {
    "agent": "loquilex-ui/0.3.0",
    "accept": ["asr.partial", "asr.final", "mt.final"],
    "ack_mode": "cumulative",
    "max_in_flight": 32
  }
}
```

#### ASR Partial

```json
{
  "v": 1,
  "t": "asr.partial",
  "sid": "sess_abc123",
  "id": "msg_001",
  "seq": 1,
  "t_wall": "2024-11-01T03:00:01.234Z",
  "t_mono_ns": 1234567890,
  "data": {
    "text": "Hello world this is",
    "final": false,
    "segment_id": "seg_001",
    "stability": 0.85
  }
}
```

#### ASR Final

```json
{
  "v": 1,
  "t": "asr.final",
  "sid": "sess_abc123",
  "id": "msg_002",
  "seq": 2,
  "t_wall": "2024-11-01T03:00:02.456Z",
  "t_mono_ns": 2456789012,
  "data": {
    "text": "Hello world, this is a complete sentence.",
    "segment_id": "seg_001",
    "start_ms": 0,
    "end_ms": 2456,
    "segments": [
      {
        "text": "Hello world,",
        "start": 0.0,
        "end": 1.2
      },
      {
        "text": "this is a complete sentence.",
        "start": 1.2,
        "end": 2.456
      }
    ],
    "final_seq_range": {
      "from": 1,
      "to": 2
    }
  }
}
```

#### MT Final

```json
{
  "v": 1,
  "t": "mt.final",
  "sid": "sess_abc123",
  "id": "msg_003",
  "seq": 3,
  "t_wall": "2024-11-01T03:00:02.789Z",
  "t_mono_ns": 2789012345,
  "data": {
    "text": "你好世界，这是一个完整的句子。",
    "src": "eng_Latn",
    "tgt": "zho_Hans",
    "segment_id": "seg_001",
    "final_seq_range": {
      "from": 3,
      "to": 3
    }
  }
}
```

#### Server Heartbeat

```json
{
  "v": 1,
  "t": "server.hb",
  "sid": "sess_abc123",
  "id": "msg_hb_001",
  "seq": 100,
  "t_wall": "2024-11-01T03:00:10.000Z",
  "data": {
    "ts": "2024-11-01T03:00:10.000Z",
    "q_out": 3,
    "q_in": 0,
    "latency_ms_est": null
  }
}
```

#### Client Acknowledgement

```json
{
  "v": 1,
  "t": "client.ack",
  "data": {
    "ack_seq": 50
  }
}
```

#### Session Resume Request

```json
{
  "v": 1,
  "t": "session.resume",
  "corr": "resume_req_001",
  "data": {
    "session_id": "sess_abc123",
    "last_seq": 50,
    "epoch": 1
  }
}
```

#### Session Snapshot Response

```json
{
  "v": 1,
  "t": "session.snapshot",
  "sid": "sess_abc123",
  "id": "msg_snap_001",
  "seq": 51,
  "corr": "resume_req_001",
  "t_wall": "2024-11-01T03:00:15.000Z",
  "data": {
    "session_id": "sess_abc123",
    "epoch": 1,
    "current_seq": 51,
    "finalized_transcript": [
      {
        "text": "Hello world, this is a complete sentence.",
        "segment_id": "seg_001",
        "start_ms": 0,
        "end_ms": 2456
      }
    ],
    "active_partials": [],
    "mt_status": {
      "status": "active",
      "pending_count": 0
    }
  }
}
```

#### Error Message

```json
{
  "v": 1,
  "t": "server.error",
  "sid": "sess_abc123",
  "id": "msg_err_001",
  "seq": 999,
  "t_wall": "2024-11-01T03:00:20.000Z",
  "data": {
    "code": "invalid_ack",
    "detail": "Ack 100 beyond latest delivered seq 50",
    "retry_after_ms": null
  }
}
```

### WebSocket Reconnection & Resume

LoquiLex supports session resume after WebSocket disconnection:

1. **Client reconnects** within resume window (default 10 seconds)
2. **Client sends** `session.resume` with last received `seq`
3. **Server responds** with:
   - `session.snapshot` + replay buffer (if resume successful)
   - `session.new` (if resume expired or epoch mismatch)
4. **Client rehydrates** UI state from snapshot
5. **Normal operation resumes**

### Flow Control

The WebSocket protocol implements flow control to prevent overwhelming clients:

- **Sliding Window**: Server tracks in-flight unacknowledged messages
- **Max In-Flight**: Configurable limit (default: 64 messages)
- **Acknowledgements**: Client sends `client.ack` with cumulative or per-message mode
- **Backpressure**: Server pauses sending when window is full

### Event Frequency

Real-time events are subject to rate limiting:

- **Minimum Frequency**: 2 Hz (500ms intervals)
- **Maximum Frequency**: 10 Hz (100ms intervals)
- **Default Frequency**: 5 Hz (200ms intervals)

---

## Authentication & Security

### Current Status

**Version 0.1.0**: No authentication required

LoquiLex currently operates in **trusted local environment** mode:
- Designed for single-user desktop/laptop deployment
- Backend and frontend run on localhost
- No authentication tokens required
- CORS enabled in development mode only

### Security Headers

The server enforces security headers in all responses:

- **Content-Security-Policy**: Restricts resource loading
- **Permissions-Policy**: Limits microphone access to self
- **Referrer-Policy**: No referrer sent
- **X-Content-Type-Options**: Prevents MIME sniffing

### Admin Endpoints

Some endpoints require admin token authentication:

**Endpoint:** `POST /admin/cache/clear`

**Authentication:**
```
Authorization: Bearer <token>
```

Token is set via `LX_ADMIN_TOKEN` environment variable.

### CORS Configuration

**Development Mode** (`LX_DEV=1`):
- CORS enabled for configured origins
- Default allowed origins: `http://localhost:5173`, `http://127.0.0.1:5173`
- Configure via `LLX_ALLOWED_ORIGINS` environment variable

**Production Mode** (`LX_DEV=0`):
- CORS disabled
- WebSocket same-origin policy enforced
- Native/Electron clients with missing `Origin` header are allowed

### Future Authentication (Planned)

For multi-user or remote deployments:
- JWT-based authentication
- API key support
- OAuth2 integration
- Role-based access control (RBAC)

---

## Configuration

### Environment Variables

#### Server Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `LX_API_PORT` | `8000` | FastAPI server port |
| `LX_UI_PORT` | `5173` | Frontend development server port (Vite) |
| `LX_DEV` | `0` | Enable development mode (CORS, verbose logging) |
| `LX_WS_PATH` | `/ws` | WebSocket endpoint path |
| `LX_WS_ALLOW_EVENTS_ALIAS` | `0` | Enable legacy `/events` WebSocket path |

#### Storage Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `LLX_OUT_DIR` | `loquilex/out` | Output directory for sessions, exports, profiles |
| `LX_EXPORT_TTL_HOURS` | `72` | Time-to-live for exported files (hours) |
| `LX_EXPORT_MAX_MB` | `0` | Maximum storage for exports (MB, 0=unlimited) |
| `LX_EXPORT_SWEEP_INTERVAL_S` | `300` | Retention sweep interval (seconds) |
| `LX_ALLOWED_STORAGE_ROOTS` | `/tmp` | Colon-separated allowed storage roots |

#### WebSocket Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `LX_WS_HEARTBEAT_SEC` | `5.0` | Heartbeat interval (seconds) |
| `LX_WS_HEARTBEAT_TIMEOUT_SEC` | `15.0` | Heartbeat timeout (seconds) |
| `LX_WS_RESUME_TTL` | `10.0` | Resume window duration (seconds) |
| `LX_WS_RESUME_MAX_EVENTS` | `500` | Maximum events in resume buffer |
| `LX_WS_MAX_IN_FLIGHT` | `64` | Maximum unacknowledged messages |
| `LX_WS_MAX_MSG_BYTES` | `131072` | Maximum message size (bytes) |
| `LX_CLIENT_EVENT_BUFFER` | `300` | Client-side event buffer size |

#### Session Storage Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `LX_SESSION_MAX_COMMITS` | `100` | Maximum session history commits |
| `LX_SESSION_MAX_SIZE_BYTES` | `1048576` | Maximum session storage size (bytes) |
| `LX_SESSION_MAX_AGE_SECONDS` | `3600.0` | Maximum session history age (seconds) |

#### Model & ML Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `LX_ASR_MODEL` | `small.en` | Default ASR model |
| `LX_ASR_LANGUAGE` | `en` | Default ASR language |
| `LX_DEVICE` | `auto` | Default compute device (`auto`, `cuda`, `cpu`) |
| `LX_SKIP_MODEL_PREFETCH` | `0` | Skip model downloads during setup |
| `LX_OFFLINE` | `0` | Enable offline mode (no network calls) |

#### Security & Administration

| Variable | Default | Description |
|----------|---------|-------------|
| `LX_ADMIN_TOKEN` | (none) | Admin API token |
| `LLX_ALLOWED_ORIGINS` | `http://localhost:5173,http://127.0.0.1:5173` | CORS allowed origins (comma-separated) |

### Example Configuration

**Development Setup:**
```bash
export LX_DEV=1
export LX_API_PORT=8000
export LX_UI_PORT=5173
export LLX_OUT_DIR="./output"
export LX_ASR_MODEL="small.en"
export LX_DEVICE="auto"
export LX_SKIP_MODEL_PREFETCH=1
```

**Production Setup:**
```bash
export LX_DEV=0
export LX_API_PORT=8000
export LLX_OUT_DIR="/var/lib/loquilex/data"
export LX_ASR_MODEL="base.en"
export LX_DEVICE="cuda"
export LX_ADMIN_TOKEN="your-secure-token-here"
export LX_EXPORT_TTL_HOURS=24
export LX_EXPORT_MAX_MB=5000
```

---

## Deployment

### Prerequisites

- **Python**: 3.10 or higher
- **Operating System**: Linux, macOS, or Windows
- **Memory**: 4GB+ RAM (8GB+ recommended for ML models)
- **Storage**: 2GB+ free disk space (for ML models)
- **GPU** (optional): CUDA-capable GPU for hardware acceleration

### Installation

```bash
# Clone repository
git clone https://github.com/Guffawaffle/LoquiLex.git
cd LoquiLex

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -e .

# OR minimal offline setup (no ML models)
make dev-minimal

# OR full setup with ML models
make dev-ml-cpu
```

### Starting the Server

#### Development Mode

```bash
# Set environment
export LX_DEV=1
export LX_API_PORT=8000

# Start server
python -m loquilex.api.server
```

Server will be available at:
- API: `http://localhost:8000`
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

#### Production Mode (Uvicorn)

```bash
# Install uvicorn
pip install uvicorn

# Run with production settings
uvicorn loquilex.api.server:app \
  --host 0.0.0.0 \
  --port 8000 \
  --workers 4 \
  --log-level info
```

#### Docker Deployment

```bash
# Build image
docker build -t loquilex:latest .

# Run container
docker run -d \
  -p 8000:8000 \
  -v /path/to/output:/app/output \
  -e LX_API_PORT=8000 \
  -e LLX_OUT_DIR=/app/output \
  loquilex:latest
```

See [docs/DOCKER.md](./DOCKER.md) for detailed Docker instructions.

### Health Checks

**Readiness Check:**
```bash
curl http://localhost:8000/healthz
```

**Liveness Check:**
```bash
curl -I http://localhost:8000/api/health
```

### Monitoring

**Server Logs:**
- Structured JSON logging
- Configurable log levels via `LX_LOG_LEVEL`
- Logs written to `LX_LOG_DIR` (default: `./logs`)

**Metrics:**
- Hardware snapshot: `GET /hardware/snapshot`
- Session metrics: `GET /sessions/{sid}/metrics`
- Download status: `GET /models/downloads`

---

## Versioning & Compatibility

### API Versioning

**Current Version**: `0.1.0`

LoquiLex uses semantic versioning:
- **Major version** (0.x.x): Breaking changes to API contract
- **Minor version** (x.1.x): New features, backward compatible
- **Patch version** (x.x.1): Bug fixes, backward compatible

### Backward Compatibility Policy

**Guarantees:**
- Minor version updates maintain backward compatibility
- Deprecated features receive at least one minor version notice before removal
- WebSocket envelope version (`v`) field enables protocol evolution

**Breaking Changes:**
- Only in major version updates
- Announced in advance via changelog
- Migration guide provided

### WebSocket Envelope Versioning

The `v` field in WebSocket envelopes enables schema evolution:

```json
{
  "v": 1,  // Current schema version
  "t": "asr.partial",
  ...
}
```

**Future versions** may introduce:
- `v: 2` with enhanced payload structure
- New message types (backward compatible)
- Optional fields (non-breaking)

### Feature Flags

Experimental features can be enabled via environment variables:
- `LX_WS_ALLOW_EVENTS_ALIAS=1`: Enable legacy WebSocket path
- `LX_EXPERIMENTAL_FEATURES=1`: Enable experimental endpoints

---

## Error Handling

### HTTP Status Codes

| Code | Meaning | Usage |
|------|---------|-------|
| `200 OK` | Success | Request completed successfully |
| `400 Bad Request` | Client error | Invalid parameters or request body |
| `403 Forbidden` | Authorization error | Missing or invalid credentials |
| `404 Not Found` | Resource not found | Session, profile, or model does not exist |
| `409 Conflict` | Resource conflict | GPU busy, model already downloading |
| `500 Internal Server Error` | Server error | Unexpected server-side error |
| `503 Service Unavailable` | Service unavailable | Feature not available or temporarily down |

### Error Response Format

**HTTP Errors:**
```json
{
  "detail": "Session not found"
}
```

**HTTP Errors with Context:**
```json
{
  "detail": {
    "error": "GPU busy with another session",
    "requested_device": "cuda"
  }
}
```

### WebSocket Error Messages

**Error Envelope:**
```json
{
  "v": 1,
  "t": "server.error",
  "sid": "sess_abc123",
  "id": "msg_err_001",
  "seq": 999,
  "data": {
    "code": "invalid_ack",
    "detail": "Ack 100 beyond latest delivered seq 50",
    "retry_after_ms": null
  }
}
```

**Error Codes:**
- `internal`: Internal server error
- `bad_request`: Invalid message format
- `unauthorized`: Authentication required
- `not_found`: Resource not found
- `rate_limit`: Rate limit exceeded
- `invalid_ack`: Invalid acknowledgement sequence
- `resume_gap`: Resume window expired
- `invalid_message`: Malformed message
- `resume_expired`: Session resume timeout

### Error Handling Best Practices

**Client Implementation:**
1. Check HTTP status codes
2. Parse error `detail` for context
3. Implement exponential backoff for retries
4. Handle WebSocket `server.error` messages
5. Monitor `queue.drop` events for data loss
6. Implement reconnection logic with resume

**Server Behavior:**
1. Returns generic `500` for unhandled exceptions (no internal details exposed)
2. Logs all errors with structured logging
3. Includes correlation IDs for debugging
4. Provides actionable error messages

---

## Testing

### Manual Testing

**Test Server Startup:**
```bash
curl http://localhost:8000/healthz
```

**Test Session Creation:**
```bash
curl -X POST http://localhost:8000/sessions \
  -H "Content-Type: application/json" \
  -d '{
    "asr_model_id": "small.en",
    "mt_enabled": false,
    "device": "auto"
  }'
```

**Test WebSocket Connection:**
```javascript
const ws = new WebSocket('ws://localhost:8000/ws/sess_abc123');
ws.onmessage = (event) => {
  const envelope = JSON.parse(event.data);
  console.log('Received:', envelope.t, envelope.data);
};
```

### Automated Testing

**Run All Tests:**
```bash
make test
```

**Run API Tests:**
```bash
pytest tests/test_api_*.py -v
```

**Run E2E WebSocket Tests:**
```bash
pytest tests/test_e2e_websocket_api.py -v
```

### Contract Validation

Validate API contracts against OpenAPI schema:

```bash
# Generate OpenAPI schema
curl http://localhost:8000/openapi.json > openapi.json

# Validate with tools
npx @openapitools/openapi-generator-cli validate -i openapi.json
```

---

## Related Documentation

- **[WebSocket Protocol Details](./contracts/websocket.md)**: In-depth WebSocket message types
- **[Session Management](./contracts/session-management.md)**: Session lifecycle and operations
- **[ASR Streaming](./contracts/asr-streaming.md)**: Audio streaming and transcription events
- **[Translation Events](./contracts/translation.md)**: Machine translation protocol
- **[Models API](./contracts/models-api.md)**: Model discovery and download
- **[Downloads API](./contracts/downloads-api.md)**: Download orchestration
- **[Device Testing](./contracts/device-testing.md)**: Audio device validation
- **[Export Operations](./contracts/exports.md)**: Caption export and file generation

---

## Changelog

### Version 0.1.0 (Current)

**Initial API Release:**
- ✅ Session management (create, pause, resume, finalize, stop)
- ✅ Real-time transcription via WebSocket (ASR partials and finals)
- ✅ Machine translation support (MT finals)
- ✅ Model discovery and download orchestration
- ✅ Hardware capability detection
- ✅ Profile management (save/load session configurations)
- ✅ Storage management and retention policies
- ✅ WebSocket reconnection and session resume
- ✅ Flow control and acknowledgements
- ✅ Interactive API documentation (Swagger UI, ReDoc)

**Known Limitations:**
- No authentication/authorization (trusted local environment only)
- Single-user deployment model
- Limited cross-origin support (development mode only)

---

## Support

**Documentation:**
- [Quick Start Guide](./quickstart.md)
- [MVP User Guide](./mvp-user-guide.md)
- [Troubleshooting Guide](./troubleshooting.md)
- [Architecture Overview](./architecture/js-first.md)

**Issues & Feature Requests:**
- GitHub Issues: https://github.com/Guffawaffle/LoquiLex/issues

**Development:**
- [CI Testing Guide](../CI-TESTING.md)
- [Contribution Guidelines](../README.md)

---

**Last Updated:** 2025-11-01  
**API Version:** 0.1.0  
**Maintained by:** LoquiLex Contributors
