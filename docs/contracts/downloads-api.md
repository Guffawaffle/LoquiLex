# Downloads API Contract

## Overview

The Downloads API provides endpoints for orchestrating model downloads, monitoring progress, and managing download jobs. This API supports the JS-first architecture where JavaScript controls download workflows while Python handles the actual download execution.

## REST Endpoints

### Start Download

**POST** `/models/download`

Initiates a model download job.

#### Request
```typescript
interface DownloadReq {
  repo_id: string      // HuggingFace model repository ID
  model_type: 'asr' | 'mt' | 'embedding'
  force_redownload?: boolean
  cache_dir?: string
}
```

```json
{
  "repo_id": "openai/whisper-tiny.en",
  "model_type": "asr",
  "force_redownload": false
}
```

#### Response
```typescript
interface DownloadJobResponse {
  job_id: string
  status: 'queued' | 'downloading' | 'completed' | 'failed'
  model_info: {
    repo_id: string
    model_type: string
    estimated_size_mb?: number
    cache_path?: string
  }
}
```

```json
{
  "job_id": "job_1705123456_abc123",
  "status": "queued",
  "model_info": {
    "repo_id": "openai/whisper-tiny.en",
    "model_type": "asr",
    "estimated_size_mb": 37
  }
}
```

### Cancel Download

**DELETE** `/models/download/{job_id}`

Cancels an active download job.

#### Response
```typescript
interface DownloadCancelResp {
  job_id: string
  status: 'cancelled'
  bytes_downloaded: number
  cleanup_completed: boolean
}
```

```json
{
  "job_id": "job_1705123456_abc123",
  "status": "cancelled",
  "bytes_downloaded": 15728640,
  "cleanup_completed": true
}
```

### List Downloads

**GET** `/models/downloads`

Lists all download jobs for the current session.

#### Query Parameters
- `status?`: Filter by status (`queued`, `downloading`, `completed`, `failed`, `cancelled`)
- `limit?`: Maximum number of results (default: 50)
- `offset?`: Pagination offset (default: 0)

#### Response
```typescript
interface DownloadListResponse {
  jobs: DownloadJob[]
  total: number
  has_more: boolean
}

interface DownloadJob {
  job_id: string
  repo_id: string
  model_type: string
  status: 'queued' | 'downloading' | 'completed' | 'failed' | 'cancelled'
  progress: number        // 0-100 percentage
  bytes_downloaded: number
  total_bytes?: number
  download_speed_mbps?: number
  eta_seconds?: number
  created_at: string     // ISO8601
  started_at?: string    // ISO8601
  completed_at?: string  // ISO8601
  error_message?: string
}
```

### Get Download Status

**GET** `/models/download/{job_id}`

Gets detailed status for a specific download job.

#### Response
```typescript
interface DownloadStatusResponse extends DownloadJob {
  files: DownloadFileStatus[]
}

interface DownloadFileStatus {
  filename: string
  size_bytes: number
  downloaded_bytes: number
  status: 'pending' | 'downloading' | 'completed' | 'failed'
  checksum?: string
}
```

## WebSocket Events

Downloads API integrates with the WebSocket protocol for real-time progress updates.

### Download Started

```json
{
  "v": 1,
  "t": "model.download.started",
  "sid": "sess_1234567890abcdef",
  "data": {
    "job_id": "job_1705123456_abc123",
    "repo_id": "openai/whisper-tiny.en",
    "model_type": "asr",
    "total_bytes": 38654976,
    "estimated_duration_ms": 45000
  }
}
```

### Download Progress

```json
{
  "v": 1,
  "t": "model.download.progress",
  "sid": "sess_1234567890abcdef",
  "data": {
    "job_id": "job_1705123456_abc123",
    "repo_id": "openai/whisper-tiny.en",
    "progress": 67.5,
    "bytes_downloaded": 26091827,
    "total_bytes": 38654976,
    "download_speed_mbps": 12.4,
    "eta_seconds": 8
  }
}
```

### Download Completed

```json
{
  "v": 1,
  "t": "model.download.completed",
  "sid": "sess_1234567890abcdef",
  "data": {
    "job_id": "job_1705123456_abc123",
    "repo_id": "openai/whisper-tiny.en",
    "model_type": "asr",
    "cache_path": "/app/.cache/huggingface/transformers/openai--whisper-tiny.en",
    "duration_ms": 43250,
    "final_size_bytes": 38654976
  }
}
```

### Download Failed

```json
{
  "v": 1,
  "t": "model.download.failed",
  "sid": "sess_1234567890abcdef",
  "data": {
    "job_id": "job_1705123456_abc123",
    "repo_id": "openai/whisper-tiny.en",
    "error_code": "NETWORK_ERROR",
    "error_message": "Connection timeout after 30 seconds",
    "bytes_downloaded": 15728640,
    "retry_after_seconds": 60
  }
}
```

## Error Handling

### HTTP Status Codes
- **200**: Success
- **202**: Download job queued/started
- **400**: Invalid request (bad repo_id, unsupported model_type)
- **404**: Download job not found
- **409**: Download already in progress for this model
- **429**: Rate limit exceeded (too many concurrent downloads)
- **507**: Insufficient disk space
- **503**: Service unavailable (offline mode or network issues)

### Error Response Format
```json
{
  "error": {
    "code": "INSUFFICIENT_DISK_SPACE",
    "message": "Not enough disk space for download",
    "details": {
      "required_bytes": 38654976,
      "available_bytes": 25165824,
      "cache_dir": "/app/.cache"
    }
  }
}
```

### Common Error Codes
- `INVALID_REPO_ID`: Repository not found on HuggingFace
- `UNSUPPORTED_MODEL_TYPE`: Model type not supported
- `NETWORK_ERROR`: Network connectivity issues
- `INSUFFICIENT_DISK_SPACE`: Not enough storage available
- `DOWNLOAD_TIMEOUT`: Download exceeded timeout limit
- `CHECKSUM_MISMATCH`: Downloaded file integrity check failed
- `OFFLINE_MODE`: Downloads disabled in offline mode

## Concurrency & Rate Limiting

### Download Limits
- **Maximum concurrent downloads**: 3 per session
- **Rate limit**: 10 download requests per minute per session
- **Queue capacity**: 100 pending downloads per session

### Retry Strategy
```typescript
interface RetryConfig {
  max_attempts: 3
  base_delay_ms: 1000
  max_delay_ms: 30000
  backoff_multiplier: 2
  retry_on_codes: ['NETWORK_ERROR', 'DOWNLOAD_TIMEOUT']
}
```

## Offline Mode Behavior

When `LX_SKIP_MODEL_PREFETCH=1` is set:
- All download requests return `503 Service Unavailable`
- WebSocket events are not sent
- Downloads endpoint returns empty list
- Cached models remain available for use

## Disk Space Management

### Storage Locations
- **Default cache**: `~/.cache/huggingface/transformers/`
- **Custom cache**: Via `LX_CACHE_DIR` environment variable
- **Session outputs**: `LX_OUT_DIR` (separate from model cache)

### Cleanup Strategy
- Partial downloads are cleaned up on cancellation
- Failed downloads leave no artifacts
- Completed downloads are kept indefinitely unless manually removed

## Integration with UI Components

### TypeScript Example
```typescript
import { DownloadsStore } from '../orchestration/examples/downloads-store'

const downloadsStore = DownloadsStore.create()

// Start download
const jobId = await downloadsStore.startDownload({
  repoId: 'openai/whisper-tiny.en',
  type: 'asr'
})

// Monitor progress via WebSocket events
websocket.on('model.download.progress', (envelope) => {
  downloadsStore.updateProgress(envelope.data.job_id, envelope.data)
})
```

### Python Backend Example
```python
from loquilex.api.server import DownloadReq, DownloadJobResponse

@app.post("/models/download")
async def start_download(req: DownloadReq) -> DownloadJobResponse:
    job_id = await download_manager.start_download(
        repo_id=req.repo_id,
        model_type=req.model_type,
        force_redownload=req.force_redownload
    )
    return DownloadJobResponse(job_id=job_id, status="queued")
```

## Testing Contracts

### Mock Responses
```typescript
// Test successful download flow
const mockDownloadFlow = [
  { event: 'model.download.started', progress: 0 },
  { event: 'model.download.progress', progress: 25 },
  { event: 'model.download.progress', progress: 50 },
  { event: 'model.download.progress', progress: 75 },
  { event: 'model.download.completed', progress: 100 }
]
```

### Error Simulation
```python
# Test error scenarios
@pytest.mark.parametrize("error_type", [
    "NETWORK_ERROR",
    "INSUFFICIENT_DISK_SPACE", 
    "DOWNLOAD_TIMEOUT"
])
def test_download_error_handling(error_type):
    # Test implementation
    pass
```