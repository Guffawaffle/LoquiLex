import { SessionConfig } from '../types';

export type RestartScope = 'none' | 'app' | 'backend' | 'full';

export interface AppSettings {
  asr_model_id: string;
  mt_model_id: string;
  device: string;
  cadence_threshold: number; // Word count threshold for triggering EN→ZH translation (1-8). Lower values provide faster but potentially less accurate translations.
  show_timestamps: boolean;
}

// Restart requirements for each setting
export const RESTART_METADATA: Record<keyof AppSettings, RestartScope> = {
  asr_model_id: 'backend',
  mt_model_id: 'backend', 
  device: 'backend',
  cadence_threshold: 'none',
  show_timestamps: 'none',
};

export const DEFAULT_SETTINGS: AppSettings = {
  asr_model_id: '',
  mt_model_id: '',
  device: 'auto',
  cadence_threshold: 3, // Default: 3 (chosen as a balanced word count for EN→ZH translation)
  show_timestamps: true,
};

const SETTINGS_KEY = 'loquilex-settings';
const PENDING_CHANGES_KEY = 'loquilex-pending-changes';

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

// Pending changes management
export function savePendingChanges(changes: Partial<AppSettings>): void {
  try {
    localStorage.setItem(PENDING_CHANGES_KEY, JSON.stringify(changes));
  } catch (err) {
    console.warn('Failed to save pending changes to localStorage:', err);
  }
}

export function loadPendingChanges(): Partial<AppSettings> {
  try {
    const saved = localStorage.getItem(PENDING_CHANGES_KEY);
    if (saved) {
      const parsed = JSON.parse(saved);
      return parsed;
    }
  } catch (err) {
    console.warn('Failed to load pending changes from localStorage:', err);
  }
  return {};
}

export function clearPendingChanges(): void {
  try {
    localStorage.removeItem(PENDING_CHANGES_KEY);
  } catch (err) {
    console.warn('Failed to clear pending changes from localStorage:', err);
  }
}

// Check if any pending changes require restart
export function getRequiredRestartScope(changes: Partial<AppSettings>): RestartScope {
  let maxScope: RestartScope = 'none';
  
  for (const key in changes) {
    const setting = key as keyof AppSettings;
    const scope = RESTART_METADATA[setting];
    
    // Priority order: full > backend > app > none
    if (scope === 'full' || (scope === 'backend' && maxScope !== 'full') || 
        (scope === 'app' && maxScope === 'none')) {
      maxScope = scope;
    }
  }
  
  return maxScope;
}

// Check if a setting requires restart
export function requiresRestart(setting: keyof AppSettings): boolean {
  return RESTART_METADATA[setting] !== 'none';
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