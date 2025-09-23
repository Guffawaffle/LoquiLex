export interface ASRModel {
  id: string;
  name: string;
  size: string;
  memory_estimate?: number;
  available: boolean;
}

export interface MTModel {
  id: string;
  name: string;
  size: string;
  memory_estimate?: number;
  available: boolean;
}

export interface DeviceInfo {
  type: 'cpu' | 'cuda' | 'auto';
  name: string;
  memory?: number;
  compute_capability?: string;
}

export interface SessionConfig {
  name?: string;
  asr_model_id: string;
  mt_enabled: boolean;
  mt_model_id?: string;
  dest_lang: string;
  device: string;
  vad: boolean;
  beams: number;
  pause_flush_sec: number;
  segment_max_sec: number;
  partial_word_cap: number;
  save_audio: string;
  streaming_mode: boolean;
}

export interface CaptionLine {
  id: string;
  timestamp?: number;
  text: string;
  translation?: string;
  final: boolean;
}

export interface Metrics {
  asr_partial_latency_p50?: number;
  asr_partial_latency_p95?: number;
  asr_final_latency_p50?: number;
  asr_final_latency_p95?: number;
  mt_latency_p50?: number;
  mt_latency_p95?: number;
  queue_depth?: number;
  dropped_frames?: number;
  reconnect_count?: number;
}

export interface SessionStatus {
  status: 'idle' | 'starting' | 'running' | 'paused' | 'stopping' | 'error' | 'reconnecting';
  session_id?: string;
  device?: string;
  asr_model?: string;
  mt_model?: string;
  metrics?: Metrics;
}

export interface StorageInfo {
  path: string;
  total_bytes: number;
  free_bytes: number;
  used_bytes: number;
  percent_used: number;
  writable: boolean;
}

export interface BaseDirectoryValidation {
  path: string;
  valid: boolean;
  message: string;
}