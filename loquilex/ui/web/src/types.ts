// Shared types aligned with backend

export type AsrModel = {
  id: string
  name: string
  source?: string
  quant?: string | null
  path?: string
  size_bytes?: number
  language?: string
}

export type MtModel = {
  id: string
  name: string
  langs?: string[]
  path?: string
}

export type SelfTestResp = {
  ok: boolean
  asr_load_ms: number
  rms_avg: number
  message: string
  effective_asr_model?: string | null
  effective_device?: string | null
  effective_compute?: string | null
  sample_rate?: number | null
}

export type SessionCfg = {
  name?: string | null
  asr_model_id: string
  mt_enabled: boolean
  mt_model_id?: string | null
  dest_lang: string
  device: 'auto' | 'cuda' | 'cpu'
  vad: boolean
  beams: number
  pause_flush_sec: number
  segment_max_sec: number
  partial_word_cap: number
  save_audio: 'off' | 'wav' | 'flac'
}

export type EventMsg =
  | { type: 'hello'; sid: string; seq: number; ts_server: number; ts_session: number }
  | { type: 'status'; stage?: string; log?: string; seq: number; ts_server: number; ts_session: number }
  | { type: 'partial_en'; text: string; seq: number; ts_server: number; ts_session: number }
  | { type: 'partial_zh'; text: string; seq: number; ts_server: number; ts_session: number }
  | { type: 'final_en'; text: string; seq: number; ts_server: number; ts_session: number }
  | { type: 'final_zh'; text: string; seq: number; ts_server: number; ts_session: number }
  | { type: 'vu'; rms?: number; peak?: number; clip_pct?: number; seq: number; ts_server: number; ts_session: number }

export type DownloadMsg =
  | { type: 'download_progress'; job_id: string; repo_id: string; pct: number; seq: number; ts_server: number; ts_session: number }
  | { type: 'download_done'; job_id: string; local_path: string; seq: number; ts_server: number; ts_session: number }
  | { type: 'download_error'; job_id: string; message: string; seq: number; ts_server: number; ts_session: number }
