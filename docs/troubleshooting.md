# LoquiLex Troubleshooting Guide

## Overview

This guide covers common issues, offline-first behavior scenarios, and troubleshooting strategies for LoquiLex. The JS-first architecture means most issues fall into either JavaScript orchestration problems or Python execution problems.

## Table of Contents

- [Offline-First Behavior](#offline-first-behavior)
- [Hardware Requirements & Thresholds](#hardware-requirements--thresholds)
- [Installation & Setup Issues](#installation--setup-issues)
- [Audio & Microphone Problems](#audio--microphone-problems)
- [Model Loading & Download Issues](#model-loading--download-issues)
- [WebSocket Connection Problems](#websocket-connection-problems)
- [Performance Issues](#performance-issues)
- [Translation Errors](#translation-errors)
- [Export & File Generation Issues](#export--file-generation-issues)
- [Memory & Resource Management](#memory--resource-management)
- [Browser-Specific Issues](#browser-specific-issues)
- [Docker & Container Issues](#docker--container-issues)
- [Development & Debugging](#development--debugging)

## Offline-First Behavior

### Understanding Offline Mode

LoquiLex is designed to work without internet connectivity once models are downloaded.

#### Enabling Offline Mode
```bash
# Prevent all model downloads during setup
export LX_SKIP_MODEL_PREFETCH=1

# Use only local/cached models
export HF_HUB_OFFLINE=1
export TRANSFORMERS_OFFLINE=1
```

#### Expected Offline Behavior
- ✅ **Works Offline**: ASR transcription, translation (with cached models), UI functionality
- ❌ **Requires Internet**: Model downloads, software updates, telemetry

#### Offline Mode Indicators
```bash
# Check if running in offline mode
curl http://localhost:8000/api/health | jq '.offline_mode'

# Verify model cache status
curl http://localhost:8000/api/models/status | jq '.cached_models'
```

### Common Offline Issues

#### Issue: "Model not found" errors in offline mode
```bash
# Problem: Model not cached locally
curl http://localhost:8000/api/models/asr
# Shows: "download_required": true

# Solution: Download models before going offline
export LX_SKIP_MODEL_PREFETCH=0
make setup
# Or manually download:
python -c "
from transformers import WhisperProcessor, WhisperForConditionalGeneration
WhisperProcessor.from_pretrained('openai/whisper-tiny.en')
WhisperForConditionalGeneration.from_pretrained('openai/whisper-tiny.en')
"
```

#### Issue: WebSocket fails to connect in offline mode
```javascript
// Problem: Incorrect offline configuration
const wsUrl = 'ws://localhost:8000/ws' // ❌ Wrong
const wsUrl = 'ws://127.0.0.1:8000/ws' // ✅ Correct offline URL
```

## Hardware Requirements & Thresholds

### Overview

LoquiLex automatically detects your system hardware and evaluates it against performance thresholds. The hardware snapshot feature helps identify potential issues before starting transcription sessions.

### Hardware Detection

Access hardware information via:
- **API**: `GET /hardware/snapshot`
- **UI**: Hardware status shown in Launch Wizard
- **CLI**: `python -c "from loquilex.hardware import get_hardware_snapshot; print(get_hardware_snapshot().overall_status)"`

### System Scoring

LoquiLex assigns an overall score (0-100) and status:
- **90-100** (Excellent): Optimal for all use cases
- **75-89** (Good): Suitable for most scenarios  
- **60-74** (Fair): May have minor issues
- **45-59** (Poor): Significant limitations
- **<45** (Unusable): Major problems detected

### Configurable Thresholds

#### CPU Thresholds
```bash
# Minimum CPU cores (default: 2)
export LX_MIN_CPU_CORES=4

# Maximum CPU usage percentage (default: 80.0)
export LX_MAX_CPU_USAGE=70.0
```

#### GPU Thresholds
```bash
# Minimum GPU memory in GB (default: 4.0)
export LX_MIN_GPU_MEMORY_GB=8.0
```

#### Memory Thresholds
```bash
# Minimum system memory in GB (default: 8.0)
export LX_MIN_MEMORY_GB=16.0
```

### Common Hardware Issues

#### Issue: "CPU below threshold" warning
```bash
# Problem: Insufficient CPU cores
CPU has 1 cores, minimum recommended: 2

# Solutions:
# 1. Lower CPU threshold
export LX_MIN_CPU_CORES=1

# 2. Use lighter models
export LX_ASR_MODEL_ID="tiny.en"  # Instead of large models

# 3. Increase compute allocation (Docker/VM)
docker run --cpus="2.0" loquilex  # Allocate 2 CPU cores
```

#### Issue: "GPU memory below threshold" warning
```bash
# Problem: GPU has insufficient VRAM
GPU memory 2.0GB below threshold 4.0GB

# Solutions:
# 1. Lower GPU memory threshold
export LX_MIN_GPU_MEMORY_GB=2.0

# 2. Force CPU mode
export LX_DEVICE=cpu

# 3. Use quantized models
export LX_ASR_MODEL_ID="tiny.en"  # Lower memory usage
```

#### Issue: "No audio devices available" warning
```bash
# Problem: Audio devices not accessible
Device not accessible: [Errno 16] Device or resource busy

# Solutions:
# 1. Check audio permissions
sudo usermod -a -G audio $USER
sudo chmod 666 /dev/snd/*

# 2. Stop conflicting audio processes
pulseaudio --kill
sudo fuser -v /dev/snd/*

# 3. Test audio access directly
python -c "import sounddevice as sd; print(sd.query_devices())"
```

#### Issue: "System memory below threshold" warning
```bash
# Problem: Insufficient RAM
System memory 4.0GB below threshold 8.0GB

# Solutions:
# 1. Lower memory threshold
export LX_MIN_MEMORY_GB=4.0

# 2. Increase system memory (VM/container)
docker run --memory="8g" loquilex

# 3. Use memory-efficient models
export LX_ASR_MODEL_ID="tiny"  # Lower memory footprint
```

### Performance Recommendations

#### For Limited Hardware (Score < 60)
```bash
# Use minimal models and CPU-only processing
export LX_ASR_MODEL_ID="tiny.en"
export LX_DEVICE=cpu
export LX_MT_ENABLED=false
export LX_MIN_CPU_CORES=1
export LX_MIN_MEMORY_GB=2.0
```

#### For High Performance (Score > 75)
```bash
# Use larger models with GPU acceleration
export LX_ASR_MODEL_ID="large-v3"
export LX_DEVICE=auto  # Will use CUDA if available
export LX_MT_ENABLED=true
export LX_BEAMS=5  # Higher beam search for better quality
```

#### For Docker/Container Environments
```bash
# GPU passthrough (NVIDIA)
docker run --gpus all loquilex

# Audio device passthrough
docker run --device /dev/snd loquilex

# Memory and CPU limits
docker run --memory="8g" --cpus="4.0" loquilex
```

### Debugging Hardware Issues

#### Check Hardware Snapshot Details
```bash
# Get detailed hardware information
curl http://localhost:8000/hardware/snapshot | jq '.'

# Check specific warnings
curl http://localhost:8000/hardware/snapshot | jq '.warnings[]'

# Check GPU availability
python -c "import torch; print(f'CUDA: {torch.cuda.is_available()}')"
```

#### Validate Audio Setup
```bash
# Test microphone access
python -c "
import sounddevice as sd
try:
    sd.check_input_settings(samplerate=16000, channels=1)
    print('✓ Audio input available')
except Exception as e:
    print(f'✗ Audio error: {e}')
"
```

#### Monitor Resource Usage
```bash
# During transcription
htop  # CPU/memory usage
nvidia-smi  # GPU usage (if available)
lsof /dev/snd/*  # Audio device usage
```

## Installation & Setup Issues

### Environment Setup Problems

#### Issue: Python virtual environment not activated
```bash
# Problem symptoms
which python
# Shows: /usr/bin/python (system Python)

# Solution
cd /path/to/loquilex
source .venv/bin/activate
which python
# Should show: /path/to/loquilex/.venv/bin/python
```

#### Issue: Missing dependencies after installation
```bash
# Check installation completeness
pip list | grep -E "(fastapi|uvicorn|whisper|transformers)"

# Reinstall if missing
pip install -r requirements.txt
pip install -r requirements-ml-cpu.txt  # or requirements-ml-gpu.txt
```

#### Issue: Make commands fail
```bash
# Problem: Make not recognizing venv
make lint
# Error: /usr/bin/python3 -m ruff check loquilex tests

# Solution: Ensure .venv exists and is activated
make install-venv  # Creates .venv if missing
source .venv/bin/activate
make lint
```

### Permission Issues

#### Issue: Microphone access denied
```bash
# Browser console error:
# "NotAllowedError: Permission denied"

# Solutions:
# 1. Check browser permissions (Chrome: chrome://settings/content/microphone)
# 2. Use HTTPS in production (microphone requires secure context)
# 3. Test with explicit permission request:
```

```javascript
// Test microphone access
navigator.mediaDevices.getUserMedia({ audio: true })
  .then(stream => {
    console.log('Microphone access granted')
    stream.getTracks().forEach(track => track.stop())
  })
  .catch(err => console.error('Microphone access denied:', err))
```

#### Issue: File system permissions
```bash
# Problem: Cannot create output files
mkdir -p ~/.loquilex/outputs
chmod 755 ~/.loquilex/outputs

# Or set custom output directory
export LX_OUT_DIR=/tmp/loquilex-outputs
mkdir -p $LX_OUT_DIR
```

## Audio & Microphone Problems

### Audio Input Issues

#### Issue: No audio detected / Silent microphone
```bash
# Test audio input on system level
# Linux:
arecord -d 5 -f cd test.wav && play test.wav

# macOS:
rec test.wav trim 0 5 && play test.wav

# Windows:
# Use Sound Recorder app to test
```

#### Issue: Poor audio quality affecting transcription
```bash
# Check audio configuration
curl http://localhost:8000/api/devices | jq '.devices[]'

# Test different sample rates
export LX_ASR_SAMPLE_RATE=44100  # Try higher sample rate
export LX_ASR_SAMPLE_RATE=8000   # Try lower if high causes issues
```

#### Issue: Audio format not supported
```javascript
// Check supported formats in browser
navigator.mediaDevices.getSupportedConstraints()

// Use compatible format
const stream = await navigator.mediaDevices.getUserMedia({
  audio: {
    sampleRate: 16000,
    channelCount: 1,
    echoCancellation: false,
    noiseSuppression: false,
    autoGainControl: false
  }
})
```

### Device Detection Problems

#### Issue: Microphone not listed in device enumeration
```javascript
// Check device permissions first
const devices = await navigator.mediaDevices.enumerateDevices()
const audioInputs = devices.filter(device => device.kind === 'audioinput')

if (audioInputs.length === 0) {
  console.error('No audio input devices found')
  // Request permissions to see device labels
  await navigator.mediaDevices.getUserMedia({ audio: true })
  // Re-enumerate after permission grant
}
```

#### Issue: Device ID changes between sessions
```javascript
// Don't rely on device ID persistence
// Use device label matching instead
const preferredDevice = audioInputs.find(device =>
  device.label.includes('Headset') || device.label.includes('USB')
)
```

## Model Loading & Download Issues

### Download Failures

#### Issue: Model download timeout
```bash
# Problem: Slow network or large model
curl http://localhost:8000/api/models/download -d '{
  "repo_id": "openai/whisper-large",
  "timeout_ms": 300000  # Increase timeout to 5 minutes
}'

# Alternative: Download manually
python -c "
from huggingface_hub import snapshot_download
snapshot_download('openai/whisper-large', cache_dir='~/.cache/huggingface')
"
```

#### Issue: Insufficient disk space
```bash
# Check available space
df -h ~/.cache/huggingface
df -h $LX_OUT_DIR

# Clean up old models
rm -rf ~/.cache/huggingface/transformers/models--*old-model*

# Use smaller models
export LX_ASR_MODEL=openai/whisper-tiny.en  # 37MB instead of 1.5GB
export LX_NLLB_MODEL=facebook/nllb-200-distilled-600M  # 1.2GB instead of 4.7GB
```

#### Issue: HuggingFace Hub connection errors
```bash
# Problem: Network connectivity or rate limiting
curl -I https://huggingface.co/openai/whisper-tiny.en

# Solution: Use offline mode with pre-downloaded models
export HF_HUB_OFFLINE=1
export TRANSFORMERS_OFFLINE=1

# Or configure proxy if needed
export HF_HUB_PROXY=http://proxy.company.com:8080
```

### Model Loading Errors

#### Issue: CUDA out of memory
```bash
# Problem: GPU memory insufficient for model
export LX_DEVICE=cpu  # Force CPU usage

# Or use smaller model
export LX_ASR_MODEL=openai/whisper-tiny.en
export LX_NLLB_MODEL=facebook/nllb-200-distilled-600M

# Or use quantization
export LX_ASR_COMPUTE=int8
export LX_MT_COMPUTE_TYPE=int8
```

#### Issue: Model architecture mismatch
```python
# Problem: Trying to load incompatible model
# Check model configuration
from transformers import AutoConfig
config = AutoConfig.from_pretrained('model-name')
print(config.model_type)

# Use compatible model alternatives
COMPATIBLE_MODELS = {
    'asr': ['openai/whisper-tiny.en', 'openai/whisper-small'],
    'mt': ['facebook/nllb-200-distilled-600M', 'facebook/m2m100_418M']
}
```

## WebSocket Connection Problems

### Connection Failures

#### Issue: WebSocket connection refused
```bash
# Check if server is running
curl http://localhost:8000/health
curl http://localhost:8000/api/health

# Check WebSocket endpoint
curl -H "Connection: Upgrade" -H "Upgrade: websocket" \
     http://localhost:8000/ws

# Verify port and host
netstat -tulpn | grep 8000
```

#### Issue: CORS errors in browser
```bash
# Problem: Cross-origin restrictions
export LX_DEV=1  # Enable development CORS
# Or set specific origins:
export LLX_ALLOWED_ORIGINS="http://localhost:3000,http://127.0.0.1:3000"

# Restart server after changing CORS settings
```

#### Issue: WebSocket disconnects frequently
```javascript
// Implement robust reconnection
class ResilientWebSocket {
  constructor(url) {
    this.url = url
    this.reconnectDelay = 1000
    this.maxReconnectDelay = 30000
    this.reconnectAttempts = 0
    this.maxReconnectAttempts = 10

    this.connect()
  }

  connect() {
    this.ws = new WebSocket(this.url)

    this.ws.onopen = () => {
      console.log('WebSocket connected')
      this.reconnectAttempts = 0
      this.reconnectDelay = 1000
    }

    this.ws.onclose = () => {
      if (this.reconnectAttempts < this.maxReconnectAttempts) {
        setTimeout(() => this.reconnect(), this.reconnectDelay)
      }
    }
  }

  reconnect() {
    this.reconnectAttempts++
    this.reconnectDelay = Math.min(
      this.reconnectDelay * 2,
      this.maxReconnectDelay
    )
    this.connect()
  }
}
```

### Message Format Issues

#### Issue: Invalid WebSocket message format
```javascript
// Problem: Missing required fields
const badMessage = {
  t: 'asr.partial',
  data: { text: 'hello' }  // Missing version, session ID
}

// Solution: Use proper envelope format
const goodMessage = {
  v: 1,                    // Required: protocol version
  t: 'asr.partial',        // Required: message type
  sid: sessionId,          // Required: session ID
  seq: sequenceNumber++,   // Recommended: sequence number
  data: { text: 'hello' }  // Required: message payload
}
```

#### Issue: Message rate limiting
```javascript
// Problem: Sending too many messages too quickly
// Solution: Implement client-side throttling
const throttle = (func, limit) => {
  let inThrottle
  return function() {
    const args = arguments
    const context = this
    if (!inThrottle) {
      func.apply(context, args)
      inThrottle = true
      setTimeout(() => inThrottle = false, limit)
    }
  }
}

const throttledSend = throttle((message) => {
  websocket.send(JSON.stringify(message))
}, 100) // Maximum 10 messages per second
```

## Performance Issues

### High CPU Usage

#### Issue: Excessive CPU consumption during transcription
```bash
# Check current resource usage
top -p $(pgrep -f loquilex)

# Solutions:
export LX_ASR_MODEL=openai/whisper-tiny.en  # Use smaller model
export LX_ASR_COMPUTE=int8                  # Use quantization
export LX_ASR_CPU_THREADS=2                 # Limit CPU threads
export LX_DEVICE=cpu                        # Avoid GPU-CPU transfers
```

#### Issue: Browser tab consuming high CPU
```javascript
// Problem: UI updates too frequent
// Solution: Implement proper throttling
const updateUI = throttle((data) => {
  document.getElementById('transcript').textContent = data.text
}, 100) // Update UI at most 10 times per second

// Use Web Workers for heavy processing
const worker = new Worker('/audio-processor-worker.js')
worker.postMessage({ audioData: buffer })
```

### Memory Usage Issues

#### Issue: Memory leaks in long-running sessions
```javascript
// Problem: Event listeners and references not cleaned up
class SessionManager {
  constructor() {
    this.cleanup = []
  }

  addEventListeners() {
    const handler = (event) => this.handleEvent(event)
    websocket.addEventListener('message', handler)

    // Store for cleanup
    this.cleanup.push(() => {
      websocket.removeEventListener('message', handler)
    })
  }

  destroy() {
    // Clean up all resources
    this.cleanup.forEach(fn => fn())
    this.cleanup = []
  }
}
```

#### Issue: Audio buffer memory growth
```javascript
// Problem: Audio buffers accumulating
// Solution: Implement buffer management
class AudioBufferManager {
  constructor(maxBuffers = 10) {
    this.buffers = []
    this.maxBuffers = maxBuffers
  }

  addBuffer(buffer) {
    this.buffers.push(buffer)

    // Remove old buffers
    if (this.buffers.length > this.maxBuffers) {
      this.buffers.shift()
    }
  }

  clear() {
    this.buffers = []
  }
}
```

### Slow Response Times

#### Issue: High latency in ASR processing
```bash
# Check processing metrics
curl http://localhost:8000/api/models/status | jq '.asr_models[].performance_metrics'

# Optimization strategies:
export LX_ASR_BEAM=1                    # Reduce beam search
export LX_PARTIAL_DEBOUNCE_MS=50        # Faster partial results
export LX_DECODE_INTERVAL_SEC=0.1       # More frequent decoding

# Use GPU if available
export LX_DEVICE=cuda
export LX_ASR_COMPUTE=float16
```

## Translation Errors

### Translation Quality Issues

#### Issue: Poor translation quality
```bash
# Problem: Suboptimal model or language pair
# Check supported language pairs
curl http://localhost:8000/api/languages/mt/facebook/nllb-200-distilled-600M

# Use better model for specific language pair
export LX_NLLB_MODEL=facebook/nllb-200-3.3B  # Larger, higher quality
export LX_MT_BEAMS=5                          # More beam search paths
export LX_MT_NO_REPEAT=3                      # Prevent repetition
```

#### Issue: Translation takes too long
```bash
# Optimize for speed
export LX_M2M_MODEL=facebook/m2m100_418M     # Smaller, faster model
export LX_MT_BEAMS=1                         # Single beam
export LX_MT_MAX_INPUT=256                   # Shorter input chunks
export LX_MT_WORKERS=4                       # More parallel workers
```

### Language Detection Problems

#### Issue: Incorrect source language detection
```javascript
// Problem: Auto-detection failing
// Solution: Force source language
const translationRequest = {
  text: sourceText,
  source_language: 'en',  // Force English instead of auto-detect
  target_language: 'zh'
}
```

#### Issue: Unsupported language pair
```bash
# Check supported pairs
curl http://localhost:8000/api/languages/mt/current | \
  jq '.pairs[] | select(.source=="en" and .target=="zh")'

# Use fallback model
export LX_MT_PROVIDER=m2m100  # More language pairs
export LX_M2M_MODEL=facebook/m2m100_1.2B
```

## Export & File Generation Issues

### File Export Failures

#### Issue: Export process hangs or fails
```bash
# Check export status
curl http://localhost:8000/api/exports/export_123_status

# Common solutions:
export LX_EXPORT_TIMEOUT_MS=60000  # Increase timeout
export LX_OUT_DIR=/tmp/exports     # Use writable directory

# Check disk space
df -h $LX_OUT_DIR
```

#### Issue: Generated files are empty or corrupted
```bash
# Verify session has transcription data
curl http://localhost:8000/api/sessions/sess_123/stats | jq '.segment_count'

# Check export format compatibility
curl http://localhost:8000/api/exports/formats | jq '.supported_formats'

# Test with simple format first
curl -X POST http://localhost:8000/api/sessions/sess_123/export \
  -H "Content-Type: application/json" \
  -d '{"formats": ["txt"], "content_types": ["transcription"]}'
```

### File Download Issues

#### Issue: Download URLs expire or are inaccessible
```bash
# Problem: URLs expire after 1 hour
# Solution: Generate fresh download URL
curl http://localhost:8000/api/exports/export_123/refresh-urls

# Or download immediately after export
curl -X POST /api/sessions/sess_123/export | \
  jq -r '.files[0].download_url' | \
  xargs curl -o transcript.txt
```

## Memory & Resource Management

### Memory Pressure

#### Issue: System running out of memory
```bash
# Monitor memory usage
free -h
ps aux --sort=-%mem | head

# Reduce memory footprint
export LX_ASR_MODEL=openai/whisper-tiny.en  # 37MB vs 244MB
export LX_NLLB_MODEL=facebook/nllb-200-distilled-600M  # 1.2GB vs 4.7GB
export LX_MT_WORKERS=1                      # Reduce parallel workers
export LX_MODEL_CACHE_SIZE=1                # Limit loaded models
```

#### Issue: GPU memory exhaustion
```bash
# Check GPU memory usage
nvidia-smi

# Solutions:
export LX_DEVICE=cpu                    # Fall back to CPU
export LX_ASR_COMPUTE=int8             # Use quantization
export LX_MT_COMPUTE_TYPE=int8
export CUDA_VISIBLE_DEVICES=""         # Disable GPU
```

### Resource Cleanup

#### Issue: Temporary files accumulating
```bash
# Find temporary files
find /tmp -name "*loquilex*" -type f -mtime +1

# Clean up automatically
echo "0 2 * * * find /tmp -name '*loquilex*' -mtime +1 -delete" | crontab -

# Or set custom temp directory
export TMPDIR=/var/tmp/loquilex
mkdir -p $TMPDIR
```

#### Issue: Model cache growing too large
```bash
# Check cache size
du -sh ~/.cache/huggingface/transformers/

# Clean up old models
python -c "
from transformers.utils import cached_path
from pathlib import Path
import time

cache_dir = Path.home() / '.cache' / 'huggingface' / 'transformers'
for model_dir in cache_dir.glob('models--*'):
    # Remove if older than 30 days
    if time.time() - model_dir.stat().st_mtime > 30 * 24 * 3600:
        print(f'Removing old model: {model_dir}')
        # shutil.rmtree(model_dir)  # Uncomment to actually delete
"
```

## Browser-Specific Issues

### Chrome/Chromium

#### Issue: WebRTC audio context issues
```javascript
// Problem: AudioContext suspended
if (audioContext.state === 'suspended') {
  await audioContext.resume()
}

// Ensure user interaction before creating AudioContext
document.addEventListener('click', async () => {
  if (!audioContext) {
    audioContext = new AudioContext({ sampleRate: 16000 })
  }
}, { once: true })
```

#### Issue: CORS policy blocking WebSocket
```bash
# Start Chrome with disabled security for development
google-chrome --disable-web-security --user-data-dir=/tmp/chrome-dev
```

### Firefox

#### Issue: MediaRecorder format limitations
```javascript
// Check supported MIME types
const supportedTypes = [
  'audio/webm',
  'audio/webm;codecs=opus',
  'audio/wav',
  'audio/ogg'
].filter(type => MediaRecorder.isTypeSupported(type))

console.log('Supported types:', supportedTypes)

// Use first supported type
const mediaRecorder = new MediaRecorder(stream, {
  mimeType: supportedTypes[0]
})
```

### Safari

#### Issue: WebSocket connection limits
```javascript
// Safari limits concurrent WebSocket connections
// Implement connection pooling
class WebSocketPool {
  constructor(maxConnections = 6) {
    this.pool = []
    this.maxConnections = maxConnections
  }

  getConnection(url) {
    let connection = this.pool.find(conn => conn.url === url && conn.readyState === WebSocket.OPEN)

    if (!connection && this.pool.length < this.maxConnections) {
      connection = new WebSocket(url)
      this.pool.push(connection)
    }

    return connection
  }
}
```

## Docker & Container Issues

### Container Startup Problems

#### Issue: Container fails to start
```bash
# Check container logs
docker logs loquilex-container

# Common issues:
# 1. Port already in use
docker ps | grep 8000
# Solution: Use different port
docker run -p 8001:8000 loquilex

# 2. Volume mount permissions
docker run -v $(pwd)/outputs:/app/outputs:Z loquilex  # SELinux systems

# 3. GPU support not available
docker run --gpus all loquilex  # Requires nvidia-docker
```

#### Issue: Models not persisting between container restarts
```bash
# Mount model cache directory
docker run -v ~/.cache/huggingface:/app/.cache/huggingface loquilex

# Or use named volume
docker volume create loquilex-models
docker run -v loquilex-models:/app/.cache/huggingface loquilex
```

### Container Performance Issues

#### Issue: Slow performance in container
```bash
# Allocate more resources
docker run --memory=4g --cpus=2 loquilex

# Use host networking for better performance
docker run --network=host loquilex

# Enable GPU passthrough
docker run --gpus all -e LX_DEVICE=cuda loquilex
```

## Development & Debugging

### Debugging Tools

#### Enable Debug Logging
```bash
# Python backend logging
export LOG_LEVEL=DEBUG
export LX_DEBUG=1

# JavaScript frontend logging
localStorage.setItem('loquilex:debug', 'true')
```

#### WebSocket Message Inspection
```javascript
// Log all WebSocket messages
const originalSend = WebSocket.prototype.send
WebSocket.prototype.send = function(data) {
  console.log('WS Send:', JSON.parse(data))
  return originalSend.call(this, data)
}

websocket.addEventListener('message', (event) => {
  console.log('WS Receive:', JSON.parse(event.data))
})
```

#### Performance Profiling
```javascript
// Profile audio processing
performance.mark('audio-processing-start')
await processAudioChunk(audioData)
performance.mark('audio-processing-end')

performance.measure(
  'audio-processing-duration',
  'audio-processing-start',
  'audio-processing-end'
)

const measure = performance.getEntriesByName('audio-processing-duration')[0]
console.log(`Audio processing took ${measure.duration}ms`)
```

### Testing Issues

#### Issue: Tests failing in CI environment
```bash
# Use headless browser mode
export HEADLESS=true

# Skip GPU tests in CI
export SKIP_GPU_TESTS=1

# Use mock models for faster tests
export USE_MOCK_MODELS=1

# Run with minimal resources
export LX_ASR_MODEL=mock/tiny
export LX_MT_MODEL=mock/small
```

#### Issue: WebSocket tests timing out
```javascript
// Increase test timeouts for WebSocket operations
describe('WebSocket Integration', () => {
  jest.setTimeout(30000) // 30 second timeout

  test('connection and message flow', async () => {
    const websocket = new WebSocket('ws://localhost:8000/ws')

    // Wait for connection with timeout
    await new Promise((resolve, reject) => {
      const timeout = setTimeout(() => reject(new Error('Connection timeout')), 10000)

      websocket.onopen = () => {
        clearTimeout(timeout)
        resolve()
      }

      websocket.onerror = (error) => {
        clearTimeout(timeout)
        reject(error)
      }
    })
  })
})
```

## Getting Additional Help

### Log Collection
```bash
# Collect comprehensive logs for support
mkdir -p /tmp/loquilex-debug
journalctl -u loquilex > /tmp/loquilex-debug/system.log
docker logs loquilex-container > /tmp/loquilex-debug/container.log
curl http://localhost:8000/api/health > /tmp/loquilex-debug/health.json
curl http://localhost:8000/api/models/status > /tmp/loquilex-debug/models.json

# Browser logs (paste in browser console)
console.save = function(data, filename) {
  const blob = new Blob([JSON.stringify(data, null, 2)], {type: 'application/json'})
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
}

# Save browser logs
console.save(console.history || [], 'browser-console.json')
```

### Performance Diagnostics
```bash
# Generate performance report
curl http://localhost:8000/api/diagnostics > diagnostics.json

# System resource usage
iostat -x 1 10 > iostat.log &
sar -u 1 10 > cpu-usage.log &
free -s 1 -c 10 > memory-usage.log &
```

### Community Resources
- **GitHub Issues**: [Report bugs and request features](https://github.com/Guffawaffle/LoquiLex/issues)
- **Discussions**: [Ask questions and share solutions](https://github.com/Guffawaffle/LoquiLex/issues)
- **Documentation**: [Architecture and API guides](https://github.com/Guffawaffle/LoquiLex/tree/main/docs)

When reporting issues, please include:
1. LoquiLex version (`curl http://localhost:8000/api/health | jq '.version'`)
2. Environment details (OS, browser, Python version)
3. Configuration (relevant `LX_*` environment variables)
4. Steps to reproduce the issue
5. Error messages and logs
6. Expected vs actual behavior