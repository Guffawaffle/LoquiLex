# LoquiLex MVP User Guide

Complete workflows for live captioning and translation with LoquiLex.

## Table of Contents

- [Installation Modes](#installation-modes)
- [CLI Workflows](#cli-workflows)
- [WebSocket API Usage](#websocket-api-usage)
- [Configuration Reference](#configuration-reference)
- [Advanced Features](#advanced-features)
- [Troubleshooting](#troubleshooting)

## Installation Modes

### Development Mode (Offline-First)

```bash
# Minimal setup - no model downloads, perfect for development
export LX_SKIP_MODEL_PREFETCH=1
make dev-minimal

# Verify installation
make test
```

### Production Mode (With Models)

```bash
# Full ML stack with CPU optimization
make dev-ml-cpu

# Or install via pip
pip install -e .
```

### CI/Testing Mode

```bash
# Lightweight CI simulation (matches GitHub Actions)
make run-ci-mode

# Full local CI with all dependencies
make run-local-ci
```

## CLI Workflows

### Workflow 1: Audio File Processing

Process pre-recorded audio files:

```bash
# Step 1: Convert WAV to VTT captions
loquilex-wav-to-vtt --wav recording.wav --out captions.vtt

# Step 2: Translate captions to Chinese
loquilex-vtt-to-zh \
  --vtt captions.vtt \
  --out-text chinese.txt \
  --out-srt chinese.srt
```

**Supported formats:**
- Input: WAV files (automatically converted to 16kHz mono)
- Output: VTT (captions), SRT (subtitles), TXT (plain text)

### Workflow 2: Live Captioning Session

Real-time captioning with live translation:

```bash
# Basic live session
loquilex-live --out-prefix ./output/meeting

# Advanced options
loquilex-live \
  --out-prefix ./output/session \
  --stream-zh \
  --combined-vtt \
  --live-draft-files
```

**Live session features:**
- Real-time English speech recognition
- Live Chinese translation with debouncing
- Rolling text files with configurable limits
- VTT/SRT export on session end

### Workflow 3: Batch Processing

Process multiple files efficiently:

```bash
#!/bin/bash
# Process all WAV files in a directory
for wav in *.wav; do
  base=$(basename "$wav" .wav)
  loquilex-wav-to-vtt --wav "$wav" --out "${base}.vtt"
  loquilex-vtt-to-zh --vtt "${base}.vtt" --out-text "${base}_zh.txt" --out-srt "${base}_zh.srt"
done
```

## WebSocket API Usage

### Starting the Server

```bash
# Default configuration
python -m loquilex.api.server

# Custom port and configuration
export LX_API_PORT=8080
export LX_UI_PORT=3000
python -m loquilex.api.server
```

### Server Endpoints

| Endpoint | Method | Purpose |
|----------|---------|---------|
| `/models/asr` | GET | List available ASR models |
| `/models/mt` | GET | List available translation models |
| `/languages/mt/{model}` | GET | Supported target languages |
| `/sessions` | POST | Create new captioning session |
| `/sessions/{id}` | DELETE | Stop session |
| `/ws/{session_id}` | WebSocket | Real-time event stream |

### WebSocket Integration

The JS-first architecture uses WebSocket events for real-time communication:

```typescript
// Connect to session
const ws = new WebSocket(`ws://localhost:8000/ws/${sessionId}`);

// Listen for ASR events
ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  
  switch (data.type) {
    case 'asr.partial':
      updatePartialTranscript(data.text);
      break;
    case 'asr.final':
      addFinalTranscript(data.text, data.timestamp);
      break;
    case 'mt.result':
      displayTranslation(data.translation);
      break;
  }
};
```

**Event throttling:** JS clients automatically throttle UI updates to 2-10 Hz for smooth rendering.

## Configuration Reference

### Core Environment Variables

| Variable | Purpose | Default |
|----------|---------|---------|
| `LX_OUT_DIR` | Output directory for files | `./output` |
| `LX_ASR_MODEL` | Whisper model size | `tiny.en` |
| `LX_ASR_LANGUAGE` | Speech recognition language | `en` |
| `LX_DEVICE` | Processing device | `auto` |
| `LX_SKIP_MODEL_PREFETCH` | Skip model downloads | `unset` |

### Real-time Processing

| Variable | Purpose | Default |
|----------|---------|---------|
| `LX_PAUSE_FLUSH_SEC` | Silence detection threshold | `2.0` |
| `LX_SEGMENT_MAX_SEC` | Maximum segment duration | `30.0` |
| `LX_PARTIAL_DEBOUNCE_MS` | Partial result debouncing | `500` |

### Translation Settings

| Variable | Purpose | Default |
|----------|---------|---------|
| `LX_NLLB_MODEL` | NLLB translation model | `facebook/nllb-200-distilled-600M` |
| `LX_M2M_MODEL` | M2M fallback model | `facebook/m2m100_418M` |
| `LX_MT_BEAMS` | Translation beam size | `5` |
| `LX_LANG_VARIANT_ZH` | Chinese variant | `zh` |

## Advanced Features

### Model Management

```bash
# Prefetch specific models
export ASR_MODEL=base.en
make prefetch-asr

# List available models via API
curl http://localhost:8000/models/asr
curl http://localhost:8000/models/mt
```

### Performance Tuning

```bash
# GPU acceleration (if available)
export LX_DEVICE=cuda
export LX_ASR_COMPUTE=float16

# CPU optimization
export LX_DEVICE=cpu
export LX_ASR_COMPUTE=int8_float32
export LX_ASR_CPU_THREADS=4
```

### Output Customization

```bash
# Rolling text files with line limits
export LX_MAX_LINES=100

# Audio recording (off by default)
export LX_SAVE_AUDIO=1
export LX_SAVE_AUDIO_PATH=./recordings
```

### Session Management

The supervisor pattern ensures clean resource management:

- **Bounded queues** prevent memory leaks
- **Automatic cleanup** on session termination  
- **Graceful shutdown** preserves partial results

## Troubleshooting

### Common Issues

#### 1. Model Download Failures

```bash
# Problem: Network timeouts during model download
# Solution: Use offline mode for development
export LX_SKIP_MODEL_PREFETCH=1
make dev-minimal

# Or download manually
export HF_HUB_OFFLINE=0
python -c "from faster_whisper import WhisperModel; WhisperModel('tiny.en')"
```

#### 2. Audio Input Problems

```bash
# Problem: "No audio devices found"
# Solution: Check sounddevice configuration
python -c "import sounddevice; print(sounddevice.query_devices())"

# Install system audio libraries (Ubuntu/Debian)
sudo apt-get install portaudio19-dev python3-pyaudio

# macOS
brew install portaudio
```

#### 3. WebSocket Connection Issues

```bash
# Problem: WebSocket fails to connect
# Solution: Check server status and ports
netstat -tulpn | grep 8000

# Verify CORS settings
export LLX_ALLOWED_ORIGINS="http://localhost:3000,http://127.0.0.1:3000"
```

#### 4. Performance Issues

```bash
# Problem: High CPU usage, slow processing
# Solution: Optimize compute settings
export LX_ASR_MODEL=tiny.en          # Smaller model
export LX_ASR_COMPUTE=int8           # Lower precision
export LX_PAUSE_FLUSH_SEC=3.0        # Longer segments
```

#### 5. Translation Errors

```bash
# Problem: Chinese translation fails
# Solution: Check MT model availability
curl http://localhost:8000/models/mt

# Fallback to simpler model
export LX_M2M_MODEL=facebook/m2m100_418M
```

### Development Debugging

```bash
# Enable verbose logging
export PYTHONPATH=.
export LX_DEBUG=1

# Run tests with output
make test-e2e PYTEST_FLAGS="-v -s"

# Check WebSocket protocol
curl -v http://localhost:8000/models/asr
```

### Performance Monitoring

Key metrics to monitor:

- **WebSocket latency**: < 100ms for real-time feel
- **ASR processing time**: < 2x real-time audio duration
- **Translation latency**: < 500ms for 3-word segments
- **Memory usage**: Bounded queues prevent runaway growth

## JS-First Architecture Integration

### Client-Side Patterns

```typescript
// Throttled UI updates
class CaptionManager {
  private updateThrottle = new Throttle(100); // 10 Hz
  
  handlePartialResult(text: string) {
    this.updateThrottle.execute(() => {
      this.ui.updateDraft(text);
    });
  }
}

// Resilient WebSocket connection
class SessionManager {
  private reconnectBackoff = new ExponentialBackoff();
  
  async connect() {
    try {
      await this.establishWebSocket();
      this.reconnectBackoff.reset();
    } catch (error) {
      await this.reconnectBackoff.wait();
      this.connect(); // Retry
    }
  }
}
```

### Web Worker Integration

For smooth UI performance, use Web Workers for:

- Progress smoothing calculations
- ETA computations  
- Background state synchronization

```javascript
// Main thread
const worker = new Worker('/js/caption-worker.js');
worker.postMessage({ type: 'partial_update', text: partialText });

// Worker thread
self.addEventListener('message', (e) => {
  if (e.data.type === 'partial_update') {
    const smoothed = smoothProgress(e.data.text);
    self.postMessage({ type: 'ui_update', smoothed });
  }
});
```

## Production Deployment

### Docker Deployment

```bash
# Build production image
docker build -f Dockerfile.ci -t loquilex:latest .

# Run with GPU support
docker run --gpus all -p 8000:8000 -e LX_DEVICE=cuda loquilex:latest
```

### System Service

> **Note:** The file `scripts/loquilex.service` is an example systemd service file. You may need to create or customize this file for your environment. If it does not exist, create it based on your deployment requirements.
```bash
# Install as system service
sudo cp scripts/loquilex.service /etc/systemd/system/
sudo systemctl enable loquilex
sudo systemctl start loquilex
```

### Monitoring

```bash
# Health check endpoint
curl http://localhost:8000/health

# Metrics (if enabled)
curl http://localhost:8000/metrics
```

---

## Next Steps

- **Architecture Deep-dive**: [JS-First Architecture Guide](./architecture/js-first.md)
- **API Reference**: [WebSocket Contracts](./contracts/README.md)
- **Development**: [CI Testing Guide](../CI-TESTING.md)

For issues not covered here, check the [GitHub Issues](https://github.com/Guffawaffle/LoquiLex/issues) or open a new one.