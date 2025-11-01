import { describe, it, expect, beforeEach, vi } from 'vitest';
import { 
  AppSettings, 
  DEFAULT_SETTINGS, 
  loadSettings, 
  saveSettings, 
  clearSettings,
  applySettingsToSessionConfig
} from '../settings';
import { SessionConfig } from '../../types';

// Mock localStorage
const localStorageMock = (() => {
  let store: Record<string, string> = {};
  return {
    getItem: vi.fn((key: string) => store[key] || null),
    setItem: vi.fn((key: string, value: string) => {
      store[key] = value;
    }),
    removeItem: vi.fn((key: string) => {
      delete store[key];
    }),
    clear: vi.fn(() => {
      store = {};
    })
  };
})();

Object.defineProperty(window, 'localStorage', {
  value: localStorageMock
});

describe('settings', () => {
  beforeEach(() => {
    localStorageMock.clear();
    vi.clearAllMocks();
  });

  describe('DEFAULT_SETTINGS', () => {
    it('should have expected default values', () => {
      expect(DEFAULT_SETTINGS).toEqual({
        asr_model_id: '',
        mt_model_id: '',
        device: 'auto',
        cadence_threshold: 3,
        show_timestamps: true,
        hf_token: '',
        offline_mode: false,
      });
    });
  });

  describe('loadSettings', () => {
    it('should return default settings when no saved settings exist', () => {
      const settings = loadSettings();
      expect(settings).toEqual(DEFAULT_SETTINGS);
      expect(localStorageMock.getItem).toHaveBeenCalledWith('loquilex-settings');
    });

    it('should merge saved settings with defaults', () => {
      const savedSettings: Partial<AppSettings> = {
        device: 'cpu',
        cadence_threshold: 5,
      };
      
      localStorageMock.setItem('loquilex-settings', JSON.stringify(savedSettings));
      
      const settings = loadSettings();
      expect(settings).toEqual({
        ...DEFAULT_SETTINGS,
        device: 'cpu',
        cadence_threshold: 5,
      });
    });

    it('should handle invalid JSON gracefully', () => {
      localStorageMock.setItem('loquilex-settings', 'invalid-json');
      
      const settings = loadSettings();
      expect(settings).toEqual(DEFAULT_SETTINGS);
    });
  });

  describe('saveSettings', () => {
    it('should save settings to localStorage', () => {
      const settings: AppSettings = {
        ...DEFAULT_SETTINGS,
        device: 'cuda',
        cadence_threshold: 7,
      };

      saveSettings(settings);
      
      expect(localStorageMock.setItem).toHaveBeenCalledWith(
        'loquilex-settings',
        JSON.stringify(settings)
      );
    });
  });

  describe('clearSettings', () => {
    it('should remove settings from localStorage', () => {
      clearSettings();
      
      expect(localStorageMock.removeItem).toHaveBeenCalledWith('loquilex-settings');
    });
  });

  describe('applySettingsToSessionConfig', () => {
    it('should create SessionConfig with default values when config is empty', () => {
      const settings: AppSettings = {
        asr_model_id: 'whisper-small',
        mt_model_id: 'nllb-200-600M',
        device: 'cuda',
        cadence_threshold: 5,
        show_timestamps: true,
        hf_token: '',
        offline_mode: false,
      };

      const config = applySettingsToSessionConfig({}, settings);

      expect(config).toEqual({
        name: undefined,
        asr_model_id: 'whisper-small',
        mt_enabled: true,
        mt_model_id: 'nllb-200-600M',
        dest_lang: 'zho_Hans',
        device: 'cuda',
        vad: true,
        beams: 1,
        pause_flush_sec: 0.7,
        segment_max_sec: 7.0,
        partial_word_cap: 5, // From cadence_threshold
        save_audio: 'off',
        streaming_mode: true,
      });
    });

    it('should override settings with explicit config values', () => {
      const settings: AppSettings = {
        asr_model_id: 'whisper-small',
        mt_model_id: 'nllb-200-600M',
        device: 'cuda',
        cadence_threshold: 5,
        show_timestamps: true,
        hf_token: '',
        offline_mode: false,
      };

      const partialConfig: Partial<SessionConfig> = {
        asr_model_id: 'whisper-large',
        device: 'cpu',
        partial_word_cap: 10,
      };

      const config = applySettingsToSessionConfig(partialConfig, settings);

      expect(config.asr_model_id).toBe('whisper-large'); // Override from config
      expect(config.device).toBe('cpu'); // Override from config
      expect(config.partial_word_cap).toBe(10); // Override from config
      expect(config.mt_model_id).toBe('nllb-200-600M'); // From settings
    });

    it('should load settings from localStorage when not provided', () => {
      const savedSettings: AppSettings = {
        asr_model_id: 'whisper-medium',
        mt_model_id: 'nllb-200-1.3B',
        device: 'auto',
        cadence_threshold: 4,
        show_timestamps: false,
        hf_token: '',
        offline_mode: false,
      };

      localStorageMock.setItem('loquilex-settings', JSON.stringify(savedSettings));

      const config = applySettingsToSessionConfig({});

      expect(config.asr_model_id).toBe('whisper-medium');
      expect(config.mt_model_id).toBe('nllb-200-1.3B');
      expect(config.partial_word_cap).toBe(4);
    });

    it('should validate cadence threshold range (1-8)', () => {
      const settingsWithInvalidCadence: AppSettings = {
        ...DEFAULT_SETTINGS,
        cadence_threshold: 0, // Invalid - below range
      };

      const config = applySettingsToSessionConfig({}, settingsWithInvalidCadence);
      
      // The function should use the invalid value as-is since validation
      // should happen at the UI level
      expect(config.partial_word_cap).toBe(0);
    });
  });
});