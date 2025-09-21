/**
 * Orchestration Types - Single source of truth for contracts
 * 
 * This module provides versioned, typed contracts for REST/WS payloads,
 * state machine types, and orchestration primitives.
 * 
 * 📖 Documentation:
 * - WebSocket Protocol: /docs/contracts/websocket.md
 * - ASR Streaming: /docs/contracts/asr-streaming.md  
 * - Translation Events: /docs/contracts/translation.md
 * - Downloads API: /docs/contracts/downloads-api.md
 * - Session Management: /docs/contracts/session-management.md
 * - Models API: /docs/contracts/models-api.md
 * - Device Testing: /docs/contracts/device-testing.md
 * - Export Operations: /docs/contracts/exports.md
 */

// ===== Core Orchestration Types =====

export interface CancellationToken {
  readonly isCancelled: boolean
  cancel(): void
  throwIfCancelled(): void
  onCancelled(callback: () => void): void
}

export interface RetryConfig {
  maxAttempts: number
  initialDelay: number
  maxDelay: number
  backoffMultiplier: number
  jitter: boolean
}

export interface ConcurrencyLimiterConfig {
  maxConcurrent: number
  queueLimit: number
}

// ===== State Machine Types =====

export type AsyncOperationState = 
  | 'idle' 
  | 'pending' 
  | 'success' 
  | 'error' 
  | 'cancelled'

export interface AsyncOperation<T = unknown> {
  state: AsyncOperationState
  data?: T
  error?: Error
  startTime?: number
  endTime?: number
}

export type ConnectionState = 
  | 'disconnected' 
  | 'connecting' 
  | 'connected' 
  | 'reconnecting' 
  | 'failed'

// ===== WebSocket Envelope Types (aligned with backend) =====
// 📖 See: /docs/contracts/websocket.md

export type MessageType = 
  | 'session.hello' 
  | 'session.welcome'
  | 'session.heartbeat'
  | 'session.ack'
  | 'asr.partial'     // 📖 /docs/contracts/asr-streaming.md
  | 'asr.final'       // 📖 /docs/contracts/asr-streaming.md
  | 'mt.final'        // 📖 /docs/contracts/translation.md
  | 'status.update'
  | 'model.download.started'   // 📖 /docs/contracts/downloads-api.md
  | 'model.download.progress'  // 📖 /docs/contracts/downloads-api.md
  | 'model.download.completed' // 📖 /docs/contracts/downloads-api.md
  | 'model.download.failed'    // 📖 /docs/contracts/downloads-api.md

export interface WSEnvelope<TData = Record<string, unknown>> {
  v: number // Schema version
  t: MessageType // Message type (namespaced)
  sid?: string // Session ID (server-issued)
  id?: string // Message ID (server-unique)
  seq?: number // Sequence number per session
  corr?: string // Correlation ID for responses
  t_wall?: string // ISO8601 timestamp
  t_mono_ns?: number // Monotonic nanoseconds since session start
  data: TData // Type-specific payload
}

// ===== Event Data Types =====
// 📖 See contract documentation for detailed schemas

export interface ASRPartialData {
  text: string
  final: boolean
  segment_id: string
  stability?: number
  segments?: Array<Record<string, unknown>>
}

export interface ASRFinalData {
  text: string
  segment_id: string
  start_ms: number
  end_ms: number
  words?: Array<{
    word: string
    start: number
    end: number
    probability: number
  }>
}

export interface MTFinalData {
  text: string
  src: string
  tgt: string
  segment_id: string
  confidence?: number
}

export interface StatusData {
  stage: string
  detail?: string
  progress?: number
  eta_sec?: number
}

export interface DownloadProgressData {
  job_id: string
  repo_id: string
  pct: number
  bytes_downloaded?: number
  total_bytes?: number
  rate_bps?: number
  eta_sec?: number
}

export interface DownloadCompletedData {
  job_id: string
  local_path: string
  size_bytes?: number
  duration_sec?: number
}

export interface DownloadFailedData {
  job_id: string
  error: string
  code?: string
}

// ===== REST API Types =====  
// 📖 See: /docs/contracts/downloads-api.md, /docs/contracts/models-api.md

export interface RestResponse<T = unknown> {
  ok: boolean
  data?: T
  error?: {
    code: string
    message: string
    details?: Record<string, unknown>
  }
}

export interface DownloadJobRequest {
  repo_id: string
  type: 'asr' | 'mt'
}

export interface DownloadJobResponse {
  job_id: string
  status: 'started' | 'queued'
}

// ===== Worker Channel Types =====

export type WorkerMessageType = 
  | 'INIT'
  | 'COMPUTE_PROGRESS'
  | 'COMPUTE_ETA'
  | 'SHUTDOWN'

export interface WorkerMessage<T = unknown> {
  type: WorkerMessageType
  id: string
  data: T
}

export interface WorkerResponse<T = unknown> {
  id: string
  result?: T
  error?: string
}

export interface ProgressComputeRequest {
  samples: Array<{
    timestamp: number
    progress: number
  }>
  targetHz: number
}

export interface ProgressComputeResponse {
  smoothedProgress: number
  rate: number
  eta?: number | undefined
}

// ===== Store Action Types =====

export interface StoreAction<T = unknown> {
  type: string
  payload?: T
  meta?: {
    timestamp: number
    correlationId?: string
  }
}

// ===== Bounded Queue Config =====

export interface BoundedQueueConfig {
  maxSize: number
  dropStrategy: 'oldest' | 'newest' | 'reject'
  onDrop?: (item: unknown) => void
}

// ===== Export all types =====

export * from './legacy' // Re-export existing types for compatibility