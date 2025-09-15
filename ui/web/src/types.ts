// Enhanced types for the dual panel UI

export type ConnectionStatus = 'connected' | 'reconnecting' | 'offline'

export type Theme = 'light' | 'dark' | 'system'

export type TranscriptKind = 'partial' | 'final';
export interface TranscriptLine {
  utterance_id: string;
  segment_seq: number;
  kind: TranscriptKind;
  text: string;
  t_start_ms: number; // session-monotonic or wall; UI formats
}
}

export interface UIPreferences {
  theme: Theme
  showTimestamps: boolean
  autoscrollPaused: boolean
}

export interface SessionState {
  id: string
  name: string
  status: ConnectionStatus
  sourceLines: TranscriptLine[]
  targetLines: TranscriptLine[]
  currentPartial: {
    source?: TranscriptLine
    target?: TranscriptLine
  }
  lastActivity: number
  performanceHint?: string
}

export interface WebSocketMessage {
  v: number
  t: string
  sid?: string
  id?: string
  seq?: number
  corr?: string
  t_wall?: string
  t_mono_ns?: number
  data: any
}

export interface ASREvent {
  text: string
  segment_id: string
  final: boolean
  start_ms?: number
  end_ms?: number
  stability?: number
}

export interface MTEvent {
  text: string
  src: string
  tgt: string
  segment_id: string
  final: boolean
}

export interface VUMeterData {
  rms: number
  peak: number
  clip_pct?: number
}