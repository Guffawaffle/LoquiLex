import { SessionConfig } from '../types';

export interface ProviderConfig {
  huggingface: {
    token: string | null;
    enabled: boolean;
    has_token: boolean;
  };
}

export interface BackendConfig {
  offline: boolean;
  offline_enforced: boolean;
}

export interface AppSettings {
  asr_model_id: string;
  mt_model_id: string;
  device: string;
  cadence_threshold: number; // Word count threshold for triggering EN→ZH translation (1-8). Lower values provide faster but potentially less accurate translations.
  show_timestamps: boolean;
  // New provider and backend settings
  hf_token: string;
  offline_mode: boolean;
}

export const DEFAULT_SETTINGS: AppSettings = {
  asr_model_id: '',
  mt_model_id: '',
  device: 'auto',
  cadence_threshold: 3, // Default: 3 (chosen as a balanced word count for EN→ZH translation)
  show_timestamps: true,
  hf_token: '',
  offline_mode: false,
};

const SETTINGS_KEY = 'loquilex-settings';

export function loadSettings(): AppSettings {
  try {
    const saved = localStorage.getItem(SETTINGS_KEY);
    if (saved) {
      const parsed = JSON.parse(saved);
      return { ...DEFAULT_SETTINGS, ...parsed };
    }
  } catch (err) {
    console.warn('Failed to load settings from localStorage:', err);
  }
  return DEFAULT_SETTINGS;
}

export function saveSettings(settings: AppSettings): void {
  try {
    localStorage.setItem(SETTINGS_KEY, JSON.stringify(settings));
  } catch (err) {
    console.warn('Failed to save settings to localStorage:', err);
  }
}

export function clearSettings(): void {
  try {
    localStorage.removeItem(SETTINGS_KEY);
  } catch (err) {
    console.warn('Failed to clear settings from localStorage:', err);
  }
}

/**
 * Apply saved settings to a SessionConfig, using settings as defaults
 * while allowing per-session overrides
 */
export function applySettingsToSessionConfig(
  config: Partial<SessionConfig>,
  settings?: AppSettings
): SessionConfig {
  const savedSettings = settings || loadSettings();
  
  return {
    name: config.name,
    asr_model_id: config.asr_model_id || savedSettings.asr_model_id,
    mt_enabled: config.mt_enabled ?? true,
    mt_model_id: config.mt_model_id || savedSettings.mt_model_id,
    dest_lang: config.dest_lang || 'zho_Hans',
    device: config.device || savedSettings.device,
    vad: config.vad ?? true,
    beams: config.beams ?? 1,
    pause_flush_sec: config.pause_flush_sec ?? 0.7,
    segment_max_sec: config.segment_max_sec ?? 7.0,
    partial_word_cap: config.partial_word_cap ?? savedSettings.cadence_threshold,
    save_audio: config.save_audio || 'off',
    streaming_mode: config.streaming_mode ?? true,
  };
}

// Provider configuration API functions
export async function getProviderConfig(): Promise<{providers: ProviderConfig, backend: BackendConfig}> {
  const response = await fetch('/api/providers/config');
  if (!response.ok) {
    throw new Error('Failed to load provider configuration');
  }
  return response.json();
}

export async function setHuggingFaceToken(token: string): Promise<void> {
  const response = await fetch('/api/providers/hf/token', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ token }),
  });
  
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Unknown error' }));
    throw new Error(error.detail || 'Failed to set HuggingFace token');
  }
}

export async function removeHuggingFaceToken(): Promise<void> {
  const response = await fetch('/api/providers/hf/token', {
    method: 'DELETE',
  });
  
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Unknown error' }));
    throw new Error(error.detail || 'Failed to remove HuggingFace token');
  }
}

export async function setOfflineMode(offline: boolean): Promise<void> {
  const response = await fetch('/api/providers/offline', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ offline }),
  });
  
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Unknown error' }));
    throw new Error(error.detail || 'Failed to set offline mode');
  }
}