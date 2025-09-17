import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { ASRModel, MTModel } from '../types';
import { AppSettings, loadSettings, saveSettings, clearSettings, DEFAULT_SETTINGS } from '../utils/settings';

export function SettingsView() {
  const navigate = useNavigate();
  const [asrModels, setAsrModels] = useState<ASRModel[]>([]);
  const [mtModels, setMtModels] = useState<MTModel[]>([]);
  const [settings, setSettings] = useState<AppSettings>(DEFAULT_SETTINGS);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    loadModelsAndSettings();
  }, []);

  const loadModelsAndSettings = async () => {
    try {
      setLoading(true);
      setError(null);

      // Load models
      const [asrResponse, mtResponse] = await Promise.all([
        fetch('/models/asr'),
        fetch('/models/mt'),
      ]);

      if (!asrResponse.ok || !mtResponse.ok) {
        throw new Error('Failed to load models');
      }

      const asrData = await asrResponse.json();
      const mtData = await mtResponse.json();

      setAsrModels(asrData);
      setMtModels(mtData);

      // Load settings from localStorage
      const loadedSettings = loadSettings();
      
      // Auto-select first available models if not set
      if (!loadedSettings.asr_model_id && asrData.length > 0) {
        loadedSettings.asr_model_id = asrData[0].id;
      }
      if (!loadedSettings.mt_model_id && mtData.length > 0) {
        loadedSettings.mt_model_id = mtData[0].id;
      }
      
      setSettings(loadedSettings);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load models');
    } finally {
      setLoading(false);
    }
  };

  const saveSettingsHandler = () => {
    try {
      saveSettings(settings);
      setSaved(true);
      setTimeout(() => setSaved(false), 2000); // Hide saved message after 2 seconds
      setError(null);
    } catch (err) {
      setError('Failed to save settings');
    }
  };

  const resetSettings = () => {
    setSettings(DEFAULT_SETTINGS);
    clearSettings();
    setSaved(false);
    setError(null);
  };

  const updateSetting = <K extends keyof AppSettings>(key: K, value: AppSettings[K]) => {
    setSettings(prev => ({ ...prev, [key]: value }));
    setSaved(false);
  };

  if (loading) {
    return (
      <div className="settings-view">
        <div className="settings-view__container">
          <div className="settings-view__header">
            <h1 className="settings-view__title">Loading Settings...</h1>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="settings-view">
      <div className="settings-view__container">
        <div className="settings-view__header">
          <div className="settings-view__nav">
            <button
              type="button"
              className="btn btn-secondary"
              onClick={() => navigate('/')}
            >
              ← Back to Main
            </button>
          </div>
          <h1 className="settings-view__title">Settings</h1>
          <p className="settings-view__subtitle">
            Configure models, device, cadence, and display preferences
          </p>
        </div>

        {error && (
          <div className="p-4" style={{ background: 'var(--error)', color: 'white', borderRadius: '4px', marginBottom: '1rem' }}>
            {error}
          </div>
        )}

        {saved && (
          <div className="p-4" style={{ background: 'var(--success)', color: 'white', borderRadius: '4px', marginBottom: '1rem' }}>
            Settings saved successfully!
          </div>
        )}

        <div className="settings-form">
          <div className="form-group">
            <label className="form-group__label" htmlFor="asr-model-select">ASR Model</label>
            <p className="form-group__description">
              Choose the default speech recognition model for new sessions.
            </p>
            <select
              id="asr-model-select"
              className="select"
              value={settings.asr_model_id}
              onChange={(e) => updateSetting('asr_model_id', e.target.value)}
            >
              <option value="">Select ASR Model...</option>
              {asrModels.map((model) => (
                <option key={model.id} value={model.id}>
                  {model.name} ({model.size}) {!model.available && '- Download needed'}
                </option>
              ))}
            </select>
          </div>

          <div className="form-group">
            <label className="form-group__label" htmlFor="mt-model-select">MT Model</label>
            <p className="form-group__description">
              Choose the default translation model for new sessions.
            </p>
            <select
              id="mt-model-select"
              className="select"
              value={settings.mt_model_id}
              onChange={(e) => updateSetting('mt_model_id', e.target.value)}
            >
              <option value="">Select MT Model...</option>
              {mtModels.map((model) => (
                <option key={model.id} value={model.id}>
                  {model.name} ({model.size}) {!model.available && '- Download needed'}
                </option>
              ))}
            </select>
          </div>

          <div className="form-group">
            <label className="form-group__label" htmlFor="device-select">Device</label>
            <p className="form-group__description">
              Choose the compute device for processing. Auto detects best available option.
            </p>
            <select
              id="device-select"
              className="select"
              value={settings.device}
              onChange={(e) => updateSetting('device', e.target.value)}
            >
              <option value="auto">Auto (recommended)</option>
              <option value="cpu">CPU only</option>
              <option value="cuda">CUDA GPU</option>
            </select>
          </div>

          <div className="form-group">
            <label className="form-group__label" htmlFor="cadence-slider">
              Cadence Threshold: {settings.cadence_threshold} words
            </label>
            <p className="form-group__description">
              Number of words to accumulate before triggering EN→ZH translation (1-8).
              Lower values provide faster translation but may be less accurate.
            </p>
            <input
              id="cadence-slider"
              type="range"
              className="slider"
              min="1"
              max="8"
              value={settings.cadence_threshold}
              onChange={(e) => updateSetting('cadence_threshold', parseInt(e.target.value))}
            />
            <div className="slider-labels">
              <span>1 (Fast)</span>
              <span>8 (Accurate)</span>
            </div>
          </div>

          <div className="form-group">
            <label className="form-group__label">
              <input
                type="checkbox"
                checked={settings.show_timestamps}
                onChange={(e) => updateSetting('show_timestamps', e.target.checked)}
                style={{ marginRight: '0.5rem' }}
              />
              Show Timestamps
            </label>
            <p className="form-group__description">
              Display timestamps in the caption view and include them in exports.
            </p>
          </div>

          <div className="settings-actions">
            <button
              type="button"
              className="btn btn-primary"
              onClick={saveSettingsHandler}
            >
              Save Settings
            </button>
            <button
              type="button"
              className="btn"
              onClick={resetSettings}
            >
              Reset to Defaults
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}