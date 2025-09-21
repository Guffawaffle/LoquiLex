# Models API Contract

## Overview

The Models API provides endpoints for discovering, configuring, and managing ASR and translation models. Following the JS-first architecture, JavaScript orchestrates model selection and configuration while Python handles model loading and inference.

## Model Discovery

### List ASR Models

**GET** `/api/models/asr`

Lists available ASR (Automatic Speech Recognition) models.

#### Response
```typescript
interface ASRModelsResponse {
  models: ASRModelInfo[]
  default_model: string
  recommendations: ModelRecommendation[]
}

interface ASRModelInfo {
  model_id: string              // HuggingFace model identifier
  display_name: string          // Human-readable model name
  provider: 'openai' | 'facebook' | 'microsoft' | 'google'
  languages: string[]           // Supported language codes
  size_category: 'tiny' | 'small' | 'medium' | 'large'
  size_mb: number              // Approximate model size
  quality_score: number        // 0-100 quality rating
  speed_score: number          // 0-100 speed rating (higher = faster)
  memory_requirement_mb: number // RAM requirement
  features: {
    multilingual: boolean      // Supports multiple languages
    timestamps: boolean        // Word-level timestamps
    voice_activity_detection: boolean
    diarization: boolean       // Speaker identification
    real_time: boolean         // Suitable for streaming
  }
  hardware_requirements: {
    min_cpu_cores: number
    min_ram_mb: number
    gpu_recommended: boolean
    gpu_memory_mb?: number
  }
  benchmarks?: {
    wer_english?: number       // Word Error Rate for English
    rtf?: number              // Real-time factor (< 1.0 = real-time)
    latency_ms?: number       // Average processing latency
  }
}

interface ModelRecommendation {
  use_case: 'real_time' | 'accuracy' | 'multilingual' | 'low_resource'
  recommended_model: string
  reason: string
}
```

```json
{
  "models": [
    {
      "model_id": "openai/whisper-tiny.en",
      "display_name": "Whisper Tiny (English)",
      "provider": "openai",
      "languages": ["en"],
      "size_category": "tiny",
      "size_mb": 37,
      "quality_score": 75,
      "speed_score": 95,
      "memory_requirement_mb": 200,
      "features": {
        "multilingual": false,
        "timestamps": true,
        "voice_activity_detection": true,
        "diarization": false,
        "real_time": true
      },
      "hardware_requirements": {
        "min_cpu_cores": 2,
        "min_ram_mb": 512,
        "gpu_recommended": false
      },
      "benchmarks": {
        "wer_english": 0.045,
        "rtf": 0.3,
        "latency_ms": 150
      }
    }
  ],
  "default_model": "openai/whisper-tiny.en",
  "recommendations": [
    {
      "use_case": "real_time",
      "recommended_model": "openai/whisper-tiny.en",
      "reason": "Best balance of speed and accuracy for real-time transcription"
    }
  ]
}
```

### List Translation Models

**GET** `/api/models/mt`

Lists available machine translation models.

#### Response
```typescript
interface MTModelsResponse {
  models: MTModelInfo[]
  default_model: string
  language_pairs: LanguagePair[]
}

interface MTModelInfo {
  model_id: string              // HuggingFace model identifier
  display_name: string          // Human-readable model name
  provider: 'facebook' | 'google' | 'microsoft' | 'opus'
  architecture: 'nllb' | 'm2m' | 'mbart' | 'opus-mt'
  size_category: 'small' | 'medium' | 'large' | 'xl'
  size_mb: number              // Approximate model size
  quality_score: number        // 0-100 quality rating
  speed_score: number          // 0-100 speed rating
  memory_requirement_mb: number // RAM requirement
  supported_languages: string[] // Language codes
  language_pairs_count: number  // Total supported pairs
  features: {
    zero_shot: boolean         // Supports unseen language pairs
    document_level: boolean    // Context-aware translation
    domain_adaptation: boolean // Specialized domain support
    confidence_scores: boolean // Provides translation confidence
  }
  benchmarks?: {
    bleu_score?: number        // BLEU score for common pairs
    latency_ms?: number        // Average translation latency
    throughput_chars_per_sec?: number
  }
}

interface LanguagePair {
  source: string               // Source language code
  target: string              // Target language code
  quality_score: number       // 0-100 pair-specific quality
  supported_models: string[]  // Models supporting this pair
}
```

### Get Language Support

**GET** `/api/languages/mt/{model_id}`

Gets detailed language support information for a specific model.

#### Response
```typescript
interface LanguageSupportResponse {
  model_id: string
  languages: LanguageInfo[]
  pairs: LanguagePair[]
  recommendations: LanguageRecommendation[]
}

interface LanguageInfo {
  code: string                 // ISO 639-1 language code
  name: string                // Human-readable language name
  native_name: string         // Language name in native script
  script: string              // Writing system (Latin, Cyrillic, etc.)
  direction: 'ltr' | 'rtl'    // Text direction
  quality_tier: 'high' | 'medium' | 'low'  // Model quality for this language
  resource_level: 'high' | 'medium' | 'low' // Training data availability
  variants?: {
    code: string              // Variant code (e.g., zh-CN, zh-TW)
    name: string              // Variant name
    region: string            // Geographical region
  }[]
}

interface LanguageRecommendation {
  source_language: string
  recommended_targets: string[]
  reason: string
}
```

## Model Configuration

### Get Current Model Config

**GET** `/api/sessions/{session_id}/models/config`

Retrieves current model configuration for a session.

#### Response
```typescript
interface ModelConfig {
  asr: {
    model_id: string
    language?: string           // Force specific language
    task: 'transcribe' | 'translate'
    parameters: {
      beam_size: number
      best_of: number
      temperature: number
      compression_ratio_threshold: number
      logprob_threshold: number
      no_speech_threshold: number
      condition_on_previous_text: boolean
      initial_prompt?: string
    }
    compute_config: {
      device: 'cpu' | 'cuda' | 'auto'
      compute_type: 'int8' | 'float16' | 'float32'
      cpu_threads?: number
      gpu_memory_fraction?: number
    }
  }
  mt: {
    model_id: string
    source_language?: string    // Auto-detect if not specified
    target_language: string
    parameters: {
      beam_size: number
      length_penalty: number
      no_repeat_ngram_size: number
      max_input_length: number
      max_new_tokens: number
      early_stopping: boolean
    }
    compute_config: {
      device: 'cpu' | 'cuda' | 'auto'
      compute_type: 'int8' | 'float16' | 'float32'
      batch_size: number
    }
  }
}
```

### Update Model Config

**PUT** `/api/sessions/{session_id}/models/config`

Updates model configuration for a session.

#### Request
```typescript
interface UpdateModelConfigRequest {
  asr?: Partial<ModelConfig['asr']>
  mt?: Partial<ModelConfig['mt']>
  apply_immediately?: boolean  // Apply to current session vs next
}
```

#### Response
```typescript
interface UpdateModelConfigResponse {
  updated_at: string          // ISO8601
  config: ModelConfig         // New configuration
  restart_required: boolean   // Whether services need restart
  estimated_restart_time_ms?: number
}
```

## Model Status & Health

### Get Model Status

**GET** `/api/models/status`

Gets loading status and health of all models.

#### Response
```typescript
interface ModelsStatusResponse {
  asr_models: ModelStatus[]
  mt_models: ModelStatus[]
  system_resources: {
    cpu_usage_percent: number
    memory_usage_mb: number
    gpu_memory_usage_mb?: number
    disk_cache_usage_mb: number
  }
}

interface ModelStatus {
  model_id: string
  status: 'not_loaded' | 'loading' | 'loaded' | 'error' | 'unloading'
  loaded_at?: string          // ISO8601
  memory_usage_mb: number
  inference_count: number     // Number of inferences performed
  error_message?: string
  health_check: {
    last_check: string        // ISO8601
    status: 'healthy' | 'degraded' | 'unhealthy'
    response_time_ms: number
    error_rate: number        // 0-1
  }
  performance_metrics: {
    avg_inference_time_ms: number
    p95_inference_time_ms: number
    throughput_per_second: number
    cache_hit_rate?: number
  }
}
```

### Model Health Check

**POST** `/api/models/{model_id}/health-check`

Performs a health check on a specific model.

#### Response
```typescript
interface ModelHealthCheckResponse {
  model_id: string
  status: 'healthy' | 'degraded' | 'unhealthy'
  checks: {
    loading: { status: 'pass' | 'fail', message?: string }
    inference: { status: 'pass' | 'fail', message?: string, latency_ms?: number }
    memory: { status: 'pass' | 'fail', usage_mb: number, limit_mb: number }
    gpu?: { status: 'pass' | 'fail', usage_percent?: number }
  }
  recommendations: string[]
  checked_at: string          // ISO8601
}
```

## Model Loading & Unloading

### Load Model

**POST** `/api/models/{model_id}/load`

Loads a model into memory for inference.

#### Request
```typescript
interface LoadModelRequest {
  compute_config?: {
    device?: 'cpu' | 'cuda' | 'auto'
    compute_type?: 'int8' | 'float16' | 'float32'
    optimization_level?: 'none' | 'basic' | 'aggressive'
  }
  priority?: 'low' | 'normal' | 'high'
  preload_cache?: boolean     // Warm up model caches
}
```

#### Response
```typescript
interface LoadModelResponse {
  model_id: string
  status: 'loading' | 'loaded'
  estimated_load_time_ms?: number
  memory_allocated_mb: number
  warnings: string[]
}
```

### Unload Model

**POST** `/api/models/{model_id}/unload`

Unloads a model from memory to free resources.

#### Response
```typescript
interface UnloadModelResponse {
  model_id: string
  status: 'unloaded'
  memory_freed_mb: number
  unloaded_at: string         // ISO8601
}
```

## WebSocket Events

### Model Loading Events

#### Model Load Started
```json
{
  "v": 1,
  "t": "model.load.started",
  "sid": "sess_1234567890abcdef",
  "data": {
    "model_id": "openai/whisper-tiny.en",
    "model_type": "asr",
    "estimated_load_time_ms": 5000,
    "memory_required_mb": 200
  }
}
```

#### Model Load Progress
```json
{
  "v": 1,
  "t": "model.load.progress",
  "sid": "sess_1234567890abcdef",
  "data": {
    "model_id": "openai/whisper-tiny.en",
    "progress": 65,
    "stage": "loading_weights",
    "memory_used_mb": 130
  }
}
```

#### Model Load Completed
```json
{
  "v": 1,
  "t": "model.load.completed",
  "sid": "sess_1234567890abcdef",
  "data": {
    "model_id": "openai/whisper-tiny.en",
    "model_type": "asr",
    "load_time_ms": 4750,
    "memory_usage_mb": 195,
    "ready_for_inference": true
  }
}
```

#### Model Load Failed
```json
{
  "v": 1,
  "t": "model.load.failed",
  "sid": "sess_1234567890abcdef",
  "data": {
    "model_id": "openai/whisper-tiny.en",
    "error_code": "INSUFFICIENT_MEMORY",
    "error_message": "Insufficient GPU memory to load model",
    "required_mb": 1024,
    "available_mb": 512,
    "suggestions": [
      "Use CPU instead of GPU",
      "Try int8 quantization",
      "Use a smaller model variant"
    ]
  }
}
```

## Error Handling

### Model Error Codes
- `MODEL_NOT_FOUND`: Model ID doesn't exist in registry
- `DOWNLOAD_REQUIRED`: Model not cached, download needed
- `INSUFFICIENT_MEMORY`: Not enough RAM/GPU memory
- `UNSUPPORTED_DEVICE`: Device not supported for model
- `LOADING_TIMEOUT`: Model loading exceeded timeout
- `INFERENCE_ERROR`: Error during model inference
- `CONFIGURATION_ERROR`: Invalid model parameters
- `LICENSE_ERROR`: Model license restrictions

### Error Response Format
```json
{
  "error": {
    "code": "INSUFFICIENT_MEMORY",
    "message": "Cannot load model: insufficient GPU memory",
    "details": {
      "model_id": "openai/whisper-large",
      "required_memory_mb": 2048,
      "available_memory_mb": 1024,
      "suggested_alternatives": [
        "openai/whisper-medium",
        "openai/whisper-small"
      ]
    }
  }
}
```

## Performance Optimization

### Model Caching
```typescript
interface ModelCacheConfig {
  max_models_loaded: number        // Maximum concurrent models
  cache_eviction_policy: 'lru' | 'lfu' | 'ttl'
  idle_unload_timeout_ms: number   // Auto-unload after idle time
  preload_popular_models: boolean  // Load frequently used models
  memory_pressure_threshold: 0.8  // Free models when RAM > threshold
}
```

### Inference Optimization
```typescript
interface InferenceOptimization {
  batching: {
    enabled: boolean
    max_batch_size: number
    batch_timeout_ms: number
  }
  caching: {
    result_cache_size: number      // Cache recent inference results
    prompt_cache_enabled: boolean  // Cache prompt processing
  }
  quantization: {
    enabled: boolean
    precision: 'int8' | 'float16'
    dynamic: boolean              // Runtime quantization
  }
}
```

## Integration Examples

### Model Selection UI
```typescript
import { ModelsAPI } from '../api/models'

class ModelSelector {
  private modelsAPI = new ModelsAPI()

  async loadAvailableModels() {
    const [asrModels, mtModels] = await Promise.all([
      this.modelsAPI.getASRModels(),
      this.modelsAPI.getMTModels()
    ])

    return {
      asr: this.filterByCapabilities(asrModels.models),
      mt: this.filterByLanguagePair(mtModels.models, 'en', 'zh')
    }
  }

  async switchModel(modelId: string, modelType: 'asr' | 'mt') {
    // Check if model is loaded
    const status = await this.modelsAPI.getModelStatus(modelId)

    if (status.status !== 'loaded') {
      // Start loading model
      await this.modelsAPI.loadModel(modelId)

      // Monitor loading progress
      this.monitorModelLoading(modelId)
    }

    // Update session configuration
    await this.modelsAPI.updateModelConfig({
      [modelType]: { model_id: modelId }
    })
  }
}
```

### Backend Model Manager
```python
from loquilex.models import ModelManager
from loquilex.api.server import ModelsStatusResponse

class ModelsController:
    def __init__(self):
        self.model_manager = ModelManager()

    async def get_models_status(self) -> ModelsStatusResponse:
        """Get status of all models"""
        asr_status = await self.model_manager.get_asr_status()
        mt_status = await self.model_manager.get_mt_status()

        return ModelsStatusResponse(
            asr_models=asr_status,
            mt_models=mt_status,
            system_resources=self.get_system_resources()
        )

    async def load_model(self, model_id: str, config: LoadModelRequest):
        """Load model with configuration"""
        try:
            await self.model_manager.load_model(
                model_id=model_id,
                device=config.compute_config.device,
                compute_type=config.compute_config.compute_type
            )

            # Send WebSocket notification
            await websocket_manager.broadcast({
                'v': 1,
                't': 'model.load.completed',
                'data': {
                    'model_id': model_id,
                    'ready_for_inference': True
                }
            })

        except Exception as e:
            await websocket_manager.broadcast({
                'v': 1,
                't': 'model.load.failed',
                'data': {
                    'model_id': model_id,
                    'error_message': str(e)
                }
            })
```

## Testing Contracts

### Model Loading Tests
```typescript
describe('Models API', () => {
  test('load ASR model successfully', async () => {
    const modelId = 'openai/whisper-tiny.en'

    // Start loading
    const loadResponse = await modelsAPI.loadModel(modelId)
    expect(loadResponse.status).toBe('loading')

    // Wait for completion
    const completed = await waitForWebSocketEvent('model.load.completed', {
      filter: (event) => event.data.model_id === modelId,
      timeout: 10000
    })

    expect(completed.data.ready_for_inference).toBe(true)

    // Verify model is loaded
    const status = await modelsAPI.getModelStatus(modelId)
    expect(status.status).toBe('loaded')
  })

  test('handle insufficient memory error', async () => {
    const largeModelId = 'openai/whisper-large'

    await expect(
      modelsAPI.loadModel(largeModelId)
    ).rejects.toThrow('INSUFFICIENT_MEMORY')
  })
})
```

## Environment Configuration

### Model Variables
- `LX_ASR_MODEL`: Default ASR model (default: "openai/whisper-tiny.en")
- `LX_NLLB_MODEL`: Default NLLB translation model
- `LX_M2M_MODEL`: Default M2M translation model
- `LX_MT_PROVIDER`: Translation provider ("nllb", "m2m100")

### Performance Variables
- `LX_DEVICE`: Processing device ("cpu", "cuda", "auto")
- `LX_ASR_COMPUTE`: ASR compute type ("int8", "float16", "float32")
- `LX_MT_COMPUTE_TYPE`: MT compute type
- `LX_MODEL_CACHE_SIZE`: Maximum models to keep loaded (default: 3)
- `LX_AUTO_UNLOAD_TIMEOUT_MS`: Auto-unload idle models (default: 300000)
