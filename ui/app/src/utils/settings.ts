import { SessionConfig } from '../types';

export interface AppSettings {
  asr_model_id: string;
  mt_model_id: string;
  device: string;
  cadence_threshold: number; // Word count for EN→ZH translation (1-8)  
  show_timestamps: boolean;
}

export const DEFAULT_SETTINGS: AppSettings = {
  asr_model_id: '',
  mt_model_id: '',
  device: 'auto',
  cadence_threshold: 3, // Default from PRODUCT_GOALS.md
  show_timestamps: true,
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