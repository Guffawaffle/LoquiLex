# ASR Streaming Contract

## Overview

The ASR (Automatic Speech Recognition) Streaming API provides real-time transcription of audio input via WebSocket events. This contract defines the message types, timing constraints, and data structures for live speech-to-text processing in the JS-first architecture.

## WebSocket Message Types

### Audio Stream Events

#### ASR Partial Result

Real-time partial transcription updates during speech recognition.

```json
{
  "v": 1,
  "t": "asr.partial",
  "sid": "sess_1234567890abcdef",
  "seq": 145,
  "t_wall": "2024-01-13T14:30:22.150Z",
  "t_mono_ns": 15234567890,
  "data": {
    "text": "Hello, this is a partial transcri",
    "segment_id": "seg_20240113_143022_001",
    "final": false,
    "stability": 0.73,
    "language": "en",
    "confidence": 0.85,
    "words": [
      {
        "word": "Hello",
        "start_ms": 0,
        "end_ms": 420,
        "confidence": 0.96
      },
      {
        "word": "this",
        "start_ms": 500,
        "end_ms": 680,
        "confidence": 0.89
      }
    ]
  }
}
```

#### ASR Final Result

Complete transcription result for a speech segment.

```json
{
  "v": 1,
  "t": "asr.final",
  "sid": "sess_1234567890abcdef",
  "seq": 146,
  "t_wall": "2024-01-13T14:30:25.340Z",
  "t_mono_ns": 18424567890,
  "data": {
    "text": "Hello, this is a partial transcription test.",
    "segment_id": "seg_20240113_143022_001",
    "start_ms": 0,
    "end_ms": 3200,
    "language": "en",
    "confidence": 0.94,
    "words": [
      {
        "word": "Hello",
        "start_ms": 0,
        "end_ms": 420,
        "confidence": 0.96
      },
      {
        "word": "this",
        "start_ms": 500,
        "end_ms": 680,
        "confidence": 0.89
      },
      {
        "word": "is",
        "start_ms": 720,
        "end_ms": 820,
        "confidence": 0.92
      },
      {
        "word": "a",
        "start_ms": 860,
        "end_ms": 920,
        "confidence": 0.88
      },
      {
        "word": "complete",
        "start_ms": 960,
        "end_ms": 1340,
        "confidence": 0.95
      },
      {
        "word": "transcription",
        "start_ms": 1380,
        "end_ms": 2100,
        "confidence": 0.97
      },
      {
        "word": "test",
        "start_ms": 2180,
        "end_ms": 2480,
        "confidence": 0.93
      }
    ],
    "metadata": {
      "model": "openai/whisper-tiny.en",
      "sample_rate": 16000,
      "audio_duration_ms": 3200,
      "processing_time_ms": 245,
      "vad_detected": true
    }
  }
}
```

## Data Structure Definitions

### ASR Partial Data
```typescript
interface ASRPartialData {
  text: string                 // Current partial transcription
  segment_id: string          // Unique segment identifier
  final: false                // Always false for partial results
  stability: number           // 0-1 confidence in current partial (optional)
  language: string            // Detected/configured language code
  confidence: number          // Overall transcription confidence 0-1
  words?: WordTiming[]        // Word-level timing (optional)
}
```

### ASR Final Data
```typescript
interface ASRFinalData {
  text: string                // Complete transcription
  segment_id: string         // Unique segment identifier
  start_ms: number           // Segment start time in milliseconds
  end_ms: number             // Segment end time in milliseconds
  language: string           // Language code (e.g., 'en', 'zh')
  confidence: number         // Overall confidence score 0-1
  words: WordTiming[]        // Word-level timing and confidence
  metadata: ASRMetadata      // Processing metadata
}

interface WordTiming {
  word: string               // The transcribed word
  start_ms: number          // Word start time relative to segment
  end_ms: number            // Word end time relative to segment
  confidence: number        // Word-level confidence 0-1
}

interface ASRMetadata {
  model: string             // ASR model identifier
  sample_rate: number       // Audio sample rate used
  audio_duration_ms: number // Actual audio segment duration
  processing_time_ms: number // Time taken to process
  vad_detected: boolean     // Voice activity detected
  no_speech_prob?: number   // Probability of no speech (0-1)
  avg_logprob?: number      // Average log probability
}
```

## Timing Contracts

### Frequency Constraints
- **Partial Updates**: 2-10 Hz (every 100-500ms)
- **Maximum Rate**: 10 Hz to prevent UI jank
- **Minimum Rate**: 2 Hz for responsive feedback
- **Debouncing**: Client should debounce rapid partials

### Segment Timing
- **Minimum Segment**: 0.5 seconds of speech
- **Maximum Segment**: 30 seconds (auto-split longer segments)
- **Pause Detection**: 2-3 second silence triggers segment finalization
- **Voice Activity**: VAD-based segment boundaries

### Processing Latency
- **Target Latency**: <200ms from audio to partial result
- **Maximum Latency**: <500ms for real-time feel
- **Processing Time**: Should be <20% of audio duration

## Audio Configuration

### Supported Formats
```typescript
interface AudioConfig {
  sample_rate: 16000 | 22050 | 44100 | 48000  // Hz
  channels: 1                                  // Mono only
  bit_depth: 16                               // 16-bit PCM
  format: 'wav' | 'webm' | 'raw'             // Container format
  chunk_size_ms: 100                         // Audio chunk duration
}
```

### Model Configuration
```typescript
interface ASRModelConfig {
  model_id: string           // e.g., "openai/whisper-tiny.en"
  language?: string          // Force specific language
  task?: 'transcribe' | 'translate'  // Whisper task type
  beam_size?: number         // Beam search width (1-10)
  best_of?: number          // Number of candidates to consider
  temperature?: number       // Sampling temperature (0-1)
  compression_ratio_threshold?: number  // Quality threshold
  logprob_threshold?: number // Confidence threshold
  no_speech_threshold?: number  // Silence detection threshold
  condition_on_previous_text?: boolean  // Use context
}
```

## Client-Side Processing

### Throttling Implementation
```typescript
import { throttle } from 'lodash'

class ASREventHandler {
  private throttledPartialUpdate = throttle(
    (partial: ASRPartialData) => this.updateUI(partial),
    100  // 10 Hz maximum
  )

  handlePartialResult(envelope: WSEnvelope<ASRPartialData>) {
    this.throttledPartialUpdate(envelope.data)
  }

  handleFinalResult(envelope: WSEnvelope<ASRFinalData>) {
    // Final results are not throttled
    this.updateTranscript(envelope.data)
  }
}
```

### State Management
```typescript
interface ASRSessionState {
  current_segment: {
    id: string
    partial_text: string
    start_time: number
    last_update: number
  } | null

  completed_segments: ASRFinalData[]

  is_processing: boolean
  model_loaded: boolean

  stats: {
    segments_processed: number
    total_audio_ms: number
    avg_confidence: number
    processing_time_total_ms: number
  }
}
```

## Error Handling

### ASR Error Events
```json
{
  "v": 1,
  "t": "asr.error",
  "sid": "sess_1234567890abcdef",
  "data": {
    "error_code": "MODEL_LOAD_FAILED",
    "error_message": "Failed to load ASR model: openai/whisper-tiny.en",
    "segment_id": "seg_20240113_143022_001",
    "recoverable": true,
    "retry_after_ms": 5000
  }
}
```

### Common Error Codes
- `MODEL_LOAD_FAILED`: ASR model couldn't be loaded
- `AUDIO_FORMAT_ERROR`: Unsupported audio format received
- `PROCESSING_TIMEOUT`: ASR processing took too long
- `INSUFFICIENT_MEMORY`: Not enough RAM for model
- `CUDA_ERROR`: GPU processing error (if applicable)
- `AUDIO_TOO_SHORT`: Segment too brief for processing
- `AUDIO_TOO_LONG`: Segment exceeds maximum duration
- `NO_SPEECH_DETECTED`: Only silence in audio segment

## Quality Metrics

### Confidence Scoring
- **0.9-1.0**: Excellent - High confidence transcription
- **0.8-0.89**: Good - Reliable transcription
- **0.7-0.79**: Fair - May contain minor errors
- **0.6-0.69**: Poor - Likely contains errors
- **<0.6**: Very Poor - Transcription unreliable

### Stability Scoring (Partials)
- **0.9-1.0**: Very stable - unlikely to change
- **0.7-0.89**: Stable - minor changes possible
- **0.5-0.69**: Moderate - significant changes possible
- **<0.5**: Unstable - transcription still developing

## Performance Monitoring

### Metrics Collection
```typescript
interface ASRPerformanceMetrics {
  latency: {
    audio_to_partial_ms: number[]    // Distribution of latencies
    audio_to_final_ms: number[]      // Final result latencies
    p50_latency_ms: number           // Median latency
    p95_latency_ms: number           // 95th percentile
  }

  accuracy: {
    avg_confidence: number           // Mean confidence score
    low_confidence_segments: number  // Count of <0.7 confidence
    word_error_rate?: number         // WER if ground truth available
  }

  throughput: {
    segments_per_minute: number      // Processing rate
    real_time_factor: number         // Processing speed vs real-time
    audio_processed_hours: number    // Total audio processed
  }
}
```

### Performance Alerts
```json
{
  "v": 1,
  "t": "asr.performance.alert",
  "sid": "sess_1234567890abcdef",
  "data": {
    "alert_type": "HIGH_LATENCY",
    "current_value": 850,
    "threshold": 500,
    "metric": "p95_latency_ms",
    "recommendation": "Consider using a smaller ASR model or increasing processing resources"
  }
}
```

## Testing Contracts

### Mock ASR Events
```typescript
const mockASRSequence = [
  {
    type: 'asr.partial',
    data: { text: 'Hello', stability: 0.6, confidence: 0.8 }
  },
  {
    type: 'asr.partial',
    data: { text: 'Hello world', stability: 0.8, confidence: 0.85 }
  },
  {
    type: 'asr.final',
    data: {
      text: 'Hello world, this is a test.',
      confidence: 0.92,
      start_ms: 0,
      end_ms: 2500
    }
  }
]
```

### Integration Tests
```python
@pytest.mark.asyncio
async def test_asr_streaming_contract():
    """Test ASR streaming follows timing and format contracts"""

    # Test partial result frequency
    partials = await capture_partials(duration_seconds=5)
    frequency = len(partials) / 5
    assert 2 <= frequency <= 10, f"Partial frequency {frequency}Hz out of range"

    # Test message format
    for partial in partials:
        assert validate_asr_partial(partial.data)

    # Test final result
    final = await wait_for_final()
    assert validate_asr_final(final.data)
    assert final.data.confidence > 0.0
```

## Environment Configuration

### ASR Model Variables
- `LX_ASR_MODEL`: Model ID (default: "openai/whisper-tiny.en")
- `LX_ASR_LANGUAGE`: Force language (default: auto-detect)
- `LX_ASR_COMPUTE`: Compute type ("int8", "float16", "float32")
- `LX_ASR_BEAM`: Beam search size (default: 1)
- `LX_ASR_SAMPLE_RATE`: Audio sample rate (default: 16000)

### Timing Variables
- `LX_PARTIAL_DEBOUNCE_MS`: Partial result debouncing (default: 100)
- `LX_SEGMENT_MAX_SEC`: Maximum segment duration (default: 30)
- `LX_PAUSE_FLUSH_SEC`: Silence before segment finalization (default: 2.5)

### Performance Variables
- `LX_ASR_CPU_THREADS`: CPU threads for inference (default: auto)
- `LX_DEVICE`: Processing device ("cpu", "cuda", "auto")
- `LX_ASR_VAD`: Voice activity detection ("true", "false")