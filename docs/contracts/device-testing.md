# Device Testing API Contract

## Overview

The Device Testing API provides endpoints for validating audio input devices, testing microphone functionality, and ensuring optimal configuration for speech recognition. This supports the JS-first architecture by allowing JavaScript to orchestrate device testing while Python handles audio processing validation.

## REST Endpoints

### Start Device Test

**POST** `/api/devices/test`

Initiates an audio device functionality test.

#### Request
```typescript
interface SelfTestReq {
  device_id?: string           // Specific device ID, or null for default
  duration_seconds?: number    // Test duration (default: 3)
  sample_rate?: number         // Sample rate to test (default: 16000)
  test_types: DeviceTestType[] // Tests to perform
}

type DeviceTestType = 
  | 'connectivity'    // Can device be opened/accessed
  | 'audio_capture'   // Can capture audio data
  | 'noise_level'     // Background noise assessment  
  | 'frequency_response' // Frequency range validation
  | 'asr_compatibility'  // ASR model compatibility
```

```json
{
  "device_id": null,
  "duration_seconds": 5,
  "sample_rate": 16000,
  "test_types": ["connectivity", "audio_capture", "noise_level", "asr_compatibility"]
}
```

#### Response
```typescript
interface SelfTestResp {
  test_id: string
  status: 'running' | 'completed' | 'failed'
  device_info: {
    device_id: string
    device_name: string
    sample_rate: number
    channels: number
    is_default: boolean
  }
  estimated_duration_ms: number
}
```

```json
{
  "test_id": "test_1705123456_def789",
  "status": "running", 
  "device_info": {
    "device_id": "0",
    "device_name": "Built-in Microphone",
    "sample_rate": 16000,
    "channels": 1,
    "is_default": true
  },
  "estimated_duration_ms": 5000
}
```

### Get Test Results

**GET** `/api/devices/test/{test_id}`

Retrieves results from a completed device test.

#### Response
```typescript
interface DeviceTestResults {
  test_id: string
  status: 'running' | 'completed' | 'failed'
  device_info: DeviceInfo
  results: {
    connectivity: ConnectivityResult
    audio_capture: AudioCaptureResult
    noise_level: NoiseLevelResult
    frequency_response: FrequencyResponseResult
    asr_compatibility: ASRCompatibilityResult
  }
  overall_score: number        // 0-100 quality score
  recommendations: string[]    // Improvement suggestions
  duration_ms: number
  completed_at?: string        // ISO8601
}

interface ConnectivityResult {
  success: boolean
  latency_ms?: number
  error_message?: string
}

interface AudioCaptureResult {
  success: boolean
  samples_captured: number
  average_amplitude: number    // 0-1 normalized
  clipping_detected: boolean
  silence_detected: boolean
  error_message?: string
}

interface NoiseLevelResult {
  success: boolean
  background_db: number        // Decibel level
  snr_estimate: number         // Signal-to-noise ratio
  noise_classification: 'quiet' | 'moderate' | 'noisy' | 'excessive'
  error_message?: string
}

interface FrequencyResponseResult {
  success: boolean
  frequency_range_hz: [number, number]  // [min, max]
  speech_band_quality: number          // 0-1 score for 300-3400 Hz
  missing_frequencies: number[]        // Critical missing frequencies
  error_message?: string
}

interface ASRCompatibilityResult {
  success: boolean
  transcription_sample?: string        // Brief test transcription
  confidence_score?: number           // 0-1 ASR confidence
  processing_time_ms?: number         // Time to process sample
  model_loaded: boolean
  error_message?: string
}
```

### List Available Devices

**GET** `/api/devices`

Lists all available audio input devices.

#### Response
```typescript
interface DeviceListResponse {
  devices: AudioDevice[]
  default_device_id: string
}

interface AudioDevice {
  device_id: string
  device_name: string
  max_channels: number
  supported_sample_rates: number[]
  is_default: boolean
  driver_info?: {
    driver_name: string
    driver_version: string
  }
}
```

```json
{
  "devices": [
    {
      "device_id": "0",
      "device_name": "Built-in Microphone",
      "max_channels": 1,
      "supported_sample_rates": [8000, 16000, 44100, 48000],
      "is_default": true
    },
    {
      "device_id": "1", 
      "device_name": "USB Headset Microphone",
      "max_channels": 1,
      "supported_sample_rates": [16000, 44100, 48000],
      "is_default": false
    }
  ],
  "default_device_id": "0"
}
```

### Test Device Configuration

**POST** `/api/devices/{device_id}/validate`

Validates specific device configuration parameters.

#### Request
```typescript
interface DeviceConfigValidation {
  sample_rate: number
  channels: number
  buffer_size_ms?: number
  format?: 'int16' | 'float32'
}
```

#### Response
```typescript
interface ValidationResult {
  device_id: string
  config_valid: boolean
  supported_alternatives?: DeviceConfigValidation[]
  performance_estimate: {
    latency_ms: number
    cpu_usage_percent: number
    reliability_score: number  // 0-1
  }
  warnings: string[]
}
```

## WebSocket Events

Device testing integrates with WebSocket for real-time progress updates.

### Test Started

```json
{
  "v": 1,
  "t": "device.test.started",
  "sid": "sess_1234567890abcdef",
  "data": {
    "test_id": "test_1705123456_def789",
    "device_name": "Built-in Microphone",
    "test_types": ["connectivity", "audio_capture", "noise_level"],
    "estimated_duration_ms": 5000
  }
}
```

### Test Progress

```json
{
  "v": 1,
  "t": "device.test.progress",
  "sid": "sess_1234567890abcdef", 
  "data": {
    "test_id": "test_1705123456_def789",
    "progress": 60,
    "current_test": "noise_level",
    "interim_results": {
      "connectivity": { "success": true, "latency_ms": 12 },
      "audio_capture": { 
        "success": true, 
        "samples_captured": 48000,
        "average_amplitude": 0.15
      }
    }
  }
}
```

### Test Completed

```json
{
  "v": 1,
  "t": "device.test.completed",
  "sid": "sess_1234567890abcdef",
  "data": {
    "test_id": "test_1705123456_def789",
    "overall_score": 85,
    "duration_ms": 4823,
    "recommendations": [
      "Consider using a noise-canceling microphone in noisy environments",
      "Audio levels are optimal for speech recognition"
    ]
  }
}
```

### Test Failed

```json
{
  "v": 1,
  "t": "device.test.failed",
  "sid": "sess_1234567890abcdef",
  "data": {
    "test_id": "test_1705123456_def789",
    "error_code": "DEVICE_ACCESS_DENIED",
    "error_message": "Microphone access denied by system",
    "failed_at_test": "connectivity",
    "suggestions": [
      "Check system permissions for microphone access",
      "Ensure no other applications are using the microphone"
    ]
  }
}
```

## Error Handling

### HTTP Status Codes
- **200**: Success
- **202**: Test started/running
- **400**: Invalid request (unsupported device, invalid parameters)
- **403**: Device access denied (permissions issue)
- **404**: Device not found or test ID not found
- **409**: Device already in use by another test/session
- **422**: Device configuration not supported
- **503**: Audio subsystem unavailable

### Common Error Codes
- `DEVICE_NOT_FOUND`: Specified device ID does not exist
- `DEVICE_ACCESS_DENIED`: System denied microphone permissions
- `DEVICE_IN_USE`: Device busy with another application
- `UNSUPPORTED_SAMPLE_RATE`: Sample rate not supported by device
- `AUDIO_DRIVER_ERROR`: Low-level audio system error
- `TEST_TIMEOUT`: Test exceeded maximum duration
- `INSUFFICIENT_AUDIO_DATA`: Not enough audio captured for analysis

## Quality Assessment

### Scoring Criteria
- **Connectivity (20%)**: Device access, latency
- **Audio Capture (25%)**: Signal quality, clipping, silence detection
- **Noise Level (20%)**: Background noise, SNR
- **Frequency Response (15%)**: Speech frequency coverage
- **ASR Compatibility (20%)**: Model performance with device

### Score Interpretation
- **90-100**: Excellent - Optimal for all use cases
- **75-89**: Good - Suitable for most scenarios
- **60-74**: Fair - May have minor issues
- **45-59**: Poor - Significant limitations
- **Below 45**: Unusable - Major problems detected

## Browser Integration

### Permissions Handling
```typescript
// Request microphone permissions
const stream = await navigator.mediaDevices.getUserMedia({
  audio: {
    deviceId: deviceId ? { exact: deviceId } : undefined,
    sampleRate: 16000,
    channelCount: 1,
    echoCancellation: false,
    noiseSuppression: false
  }
})
```

### Device Enumeration
```typescript
// List available devices
const devices = await navigator.mediaDevices.enumerateDevices()
const audioInputs = devices.filter(device => device.kind === 'audioinput')
```

## Testing Contracts

### Mock Test Results
```typescript
const mockDeviceTestResult: DeviceTestResults = {
  test_id: 'test_mock_123',
  status: 'completed',
  results: {
    connectivity: { success: true, latency_ms: 12 },
    audio_capture: { 
      success: true,
      samples_captured: 80000,
      average_amplitude: 0.18,
      clipping_detected: false,
      silence_detected: false
    },
    noise_level: {
      success: true,
      background_db: 35,
      snr_estimate: 20,
      noise_classification: 'quiet'  
    }
  },
  overall_score: 87
}
```

### Error Scenarios
```python
@pytest.mark.parametrize("error_scenario", [
    "DEVICE_ACCESS_DENIED",
    "DEVICE_NOT_FOUND", 
    "DEVICE_IN_USE",
    "TEST_TIMEOUT"
])
def test_device_error_handling(error_scenario):
    # Test error handling for different device issues
    pass
```

## Environment Variables

- `LX_AUDIO_DEVICE_ID`: Default device ID for testing
- `LX_AUDIO_SAMPLE_RATE`: Default sample rate (16000)
- `LX_DEVICE_TEST_TIMEOUT`: Maximum test duration in seconds (30)
- `LX_AUDIO_BUFFER_SIZE`: Audio buffer size in milliseconds (100)

## Platform Considerations

### Windows
- WDM/DirectSound drivers supported
- WASAPI for low-latency audio
- Windows Audio Session API integration

### macOS  
- Core Audio framework
- Audio Unit support
- Permission dialogs in macOS 10.14+

### Linux
- ALSA/PulseAudio support
- Jack compatibility
- Permission configuration via udev rules

### Browser
- WebRTC getUserMedia API
- AudioWorklet for advanced processing
- Cross-origin restrictions apply