import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { ASRModel, MTModel } from '../types';
import { 
  AppSettings, 
  loadSettings, 
  saveSettings, 
  clearSettings, 
  DEFAULT_SETTINGS,
  getProviderConfig,
  setHuggingFaceToken,
  removeHuggingFaceToken,
  setOfflineMode,
  ProviderConfig,
  BackendConfig
} from '../utils/settings';

export function SettingsView() {
  const navigate = useNavigate();
  const [asrModels, setAsrModels] = useState<ASRModel[]>([]);
  const [mtModels, setMtModels] = useState<MTModel[]>([]);
  const [settings, setSettings] = useState<AppSettings>(DEFAULT_SETTINGS);
  const [providerConfig, setProviderConfig] = useState<ProviderConfig | null>(null);
  const [backendConfig, setBackendConfig] = useState<BackendConfig | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);
  const [hfTokenInput, setHfTokenInput] = useState('');
  const [showTokenInput, setShowTokenInput] = useState(false);

  useEffect(() => {
    loadModelsAndSettings();
  }, []);

  const loadModelsAndSettings = async () => {
    try {
      setLoading(true);
      setError(null);

      // Load models and provider configuration
      const [asrResponse, mtResponse, providerData] = await Promise.all([
        fetch('/models/asr'),
        fetch('/models/mt'),
        getProviderConfig(),
      ]);

      if (!asrResponse.ok || !mtResponse.ok) {
        throw new Error('Failed to load models');
      }

      const asrData = await asrResponse.json();
      const mtData = await mtResponse.json();

      setAsrModels(asrData);
      setMtModels(mtData);
      setProviderConfig(providerData.providers);
      setBackendConfig(providerData.backend);

      // Load settings from localStorage
      const loadedSettings = loadSettings();
      
      // Auto-select first available models if not set
      const updatedSettings = { ...loadedSettings };
      if (!updatedSettings.asr_model_id && asrData.length > 0) {
        updatedSettings.asr_model_id = asrData[0].id;
      }
      if (!updatedSettings.mt_model_id && mtData.length > 0) {
        updatedSettings.mt_model_id = mtData[0].id;
      }
      
      // Update offline mode from backend
      updatedSettings.offline_mode = providerData.backend.offline;
      
      setSettings(updatedSettings);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load models and settings');
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

  const handleSetHfToken = async () => {
    if (!hfTokenInput.trim()) {
      setError('Please enter a valid HuggingFace token');
      return;
    }

    try {
      await setHuggingFaceToken(hfTokenInput.trim());
      setHfTokenInput('');
      setShowTokenInput(false);
      
      // Reload provider config
      const providerData = await getProviderConfig();
      setProviderConfig(providerData.providers);
      
      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to set HuggingFace token');
    }
  };

  const handleRemoveHfToken = async () => {
    try {
      await removeHuggingFaceToken();
      
      // Reload provider config
      const providerData = await getProviderConfig();
      setProviderConfig(providerData.providers);
      
      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to remove HuggingFace token');
    }
  };

  const handleToggleOfflineMode = async (offline: boolean) => {
    try {
      await setOfflineMode(offline);
      
      // Reload backend config
      const providerData = await getProviderConfig();
      setBackendConfig(providerData.backend);
      
      // Update local settings
      updateSetting('offline_mode', offline);
      
      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to toggle offline mode');
    }
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

          {/* Provider Configuration Section */}
          <div style={{ borderTop: '1px solid #ddd', paddingTop: '2rem', marginTop: '2rem' }}>
            <h3 className="form-group__label" style={{ fontSize: '1.2rem', marginBottom: '1rem' }}>Provider Configuration</h3>
            
            {/* HuggingFace Token */}
            <div className="form-group">
              <label className="form-group__label">HuggingFace Token</label>
              <p className="form-group__description">
                Optional access token for enhanced model access and higher rate limits.
                {providerConfig?.huggingface.has_token && ' ✓ Token configured'}
              </p>
              
              {!showTokenInput && (
                <div className="flex gap-2 items-center">
                  {providerConfig?.huggingface.has_token ? (
                    <>
                      <span className="text-sm text-green-600">Token is configured</span>
                      <button
                        type="button"
                        className="btn btn-secondary"
                        onClick={() => setShowTokenInput(true)}
                      >
                        Update Token
                      </button>
                      <button
                        type="button"
                        className="btn btn-secondary"
                        onClick={handleRemoveHfToken}
                      >
                        Remove Token
                      </button>
                    </>
                  ) : (
                    <button
                      type="button"
                      className="btn btn-secondary"
                      onClick={() => setShowTokenInput(true)}
                    >
                      Add Token
                    </button>
                  )}
                </div>
              )}
              
              {showTokenInput && (
                <div className="flex gap-2 items-center" style={{ marginTop: '0.5rem' }}>
                  <input
                    type="password"
                    className="input"
                    placeholder="hf_..."
                    value={hfTokenInput}
                    onChange={(e) => setHfTokenInput(e.target.value)}
                    style={{ flex: 1 }}
                  />
                  <button
                    type="button"
                    className="btn btn-primary"
                    onClick={handleSetHfToken}
                  >
                    Save
                  </button>
                  <button
                    type="button"
                    className="btn btn-secondary"
                    onClick={() => {
                      setShowTokenInput(false);
                      setHfTokenInput('');
                    }}
                  >
                    Cancel
                  </button>
                </div>
              )}
            </div>

            {/* Offline Mode */}
            <div className="form-group">
              <label className="form-group__label">
                <input
                  type="checkbox"
                  checked={backendConfig?.offline ?? false}
                  onChange={(e) => handleToggleOfflineMode(e.target.checked)}
                  disabled={backendConfig?.offline_enforced ?? false}
                  style={{ marginRight: '0.5rem' }}
                />
                Enable Offline Mode
              </label>
              <p className="form-group__description">
                Disable all network requests and use only cached models.
                {backendConfig?.offline_enforced && ' (Enforced by environment variable LX_OFFLINE=1)'}
              </p>
            </div>
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