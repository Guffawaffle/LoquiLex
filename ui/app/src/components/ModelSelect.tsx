import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { ASRModel, MTModel, SessionConfig } from '../types';
import { applySettingsToSessionConfig, loadSettings, saveSettings, AppSettings } from '../utils/settings';

export function ModelSelect() {
  const navigate = useNavigate();
  const [asrModels, setAsrModels] = useState<ASRModel[]>([]);
  const [mtModels, setMtModels] = useState<MTModel[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isStarting, setIsStarting] = useState(false);
  const [latencyTarget, setLatencyTarget] = useState(200); // Default 200ms

  const [config, setConfig] = useState<SessionConfig>({
    asr_model_id: '',
    mt_enabled: true,
    mt_model_id: '',
    dest_lang: 'zho_Hans',
    device: 'auto',
    vad: true,
    beams: 1,
    pause_flush_sec: 0.7,
    segment_max_sec: 7.0,
    partial_word_cap: 10,
    save_audio: 'off',
    streaming_mode: true,
  });

  useEffect(() => {
    loadModels();
    // Load saved settings and apply as defaults
    const defaultConfig = applySettingsToSessionConfig({});
    setConfig(defaultConfig);
    
    // Load latency target from settings
    const settings = loadSettings();
    setLatencyTarget(settings.audio_latency_target_ms);
  }, []);

  const loadModels = async () => {
    try {
      setLoading(true);
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

      // Auto-select first available models
      if (asrData.length > 0) {
        setConfig(prev => ({ ...prev, asr_model_id: asrData[0].id }));
      }
      if (mtData.length > 0) {
        setConfig(prev => ({ ...prev, mt_model_id: mtData[0].id }));
      }

      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load models');
    } finally {
      setLoading(false);
    }
  };

  // Helper function to save settings when user preferences change
  const updatePersistentSetting = (key: keyof AppSettings, value: any) => {
    const currentSettings = loadSettings();
    const updatedSettings = { ...currentSettings, [key]: value };
    saveSettings(updatedSettings);
  };

  const startSession = async () => {
    if (!config.asr_model_id) {
      setError('Please select an ASR model');
      return;
    }

    if (config.mt_enabled && !config.mt_model_id) {
      setError('Please select an MT model or disable translation');
      return;
    }

    try {
      setIsStarting(true);
      setError(null);

      const response = await fetch('/sessions', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(config),
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail?.error || 'Failed to create session');
      }

      const { session_id } = await response.json();
      navigate(`/session/${session_id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to start session');
    } finally {
      setIsStarting(false);
    }
  };

  if (loading) {
    return (
      <div className="model-select">
        <div className="model-select__container">
          <div className="model-select__header">
            <h1 className="model-select__title">Loading Models...</h1>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="model-select">
      <div className="model-select__container">
        <div className="model-select__header">
          <h1 className="model-select__title">LoquiLex</h1>
          <p className="model-select__subtitle">
            Live captioning and translation - local-first and offline-ready
          </p>
          <div className="model-select__nav">
            <button
              type="button"
              className="btn btn-secondary"
              onClick={() => navigate('/settings')}
            >
              ⚙️ Settings
            </button>
          </div>
        </div>

        {error && (
          <div className="p-4" style={{ background: 'var(--error)', color: 'white', borderRadius: '4px', marginBottom: '1rem' }}>
            {error}
          </div>
        )}

        <form className="model-select__form" onSubmit={(e) => { e.preventDefault(); startSession(); }}>
          <div className="form-group">
            <label className="form-group__label">ASR Model</label>
            <p className="form-group__description">
              Choose the speech recognition model. Smaller models are faster but less accurate.
            </p>
            <div className="gap-2 flex flex-col">
              {asrModels.map((model) => (
                <div
                  key={model.id}
                  className={`model-card ${config.asr_model_id === model.id ? 'model-card--selected' : ''}`}
                  onClick={() => setConfig(prev => ({ ...prev, asr_model_id: model.id }))}
                >
                  <div className="model-card__info">
                    <div className="model-card__name">{model.name}</div>
                    <div className="model-card__details">
                      Size: {model.size} {model.memory_estimate && `• ~${model.memory_estimate}MB RAM`}
                    </div>
                  </div>
                  <div className="model-card__status">
                    <div className={`status-dot ${model.available ? 'status-dot--available' : 'status-dot--unavailable'}`} />
                    {model.available ? 'Available' : 'Download needed'}
                  </div>
                </div>
              ))}
            </div>
          </div>

          <div className="form-group">
            <label className="form-group__label">
              <input
                type="checkbox"
                checked={config.mt_enabled}
                onChange={(e) => setConfig(prev => ({ ...prev, mt_enabled: e.target.checked }))}
                style={{ marginRight: '0.5rem' }}
              />
              Enable Translation
            </label>
            <p className="form-group__description">
              Translate captions to another language in real-time.
            </p>
          </div>

          {config.mt_enabled && (
            <>
              <div className="form-group">
                <label className="form-group__label">Translation Model</label>
                <div className="gap-2 flex flex-col">
                  {mtModels.map((model) => (
                    <div
                      key={model.id}
                      className={`model-card ${config.mt_model_id === model.id ? 'model-card--selected' : ''}`}
                      onClick={() => setConfig(prev => ({ ...prev, mt_model_id: model.id }))}
                    >
                      <div className="model-card__info">
                        <div className="model-card__name">{model.name}</div>
                        <div className="model-card__details">
                          Size: {model.size} {model.memory_estimate && `• ~${model.memory_estimate}MB RAM`}
                        </div>
                      </div>
                      <div className="model-card__status">
                        <div className={`status-dot ${model.available ? 'status-dot--available' : 'status-dot--unavailable'}`} />
                        {model.available ? 'Available' : 'Download needed'}
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              <div className="form-group">
                <label className="form-group__label">Target Language</label>
                <select
                  className="select"
                  value={config.dest_lang}
                  onChange={(e) => {
                    const newLang = e.target.value;
                    setConfig(prev => ({ ...prev, dest_lang: newLang }));
                    updatePersistentSetting('translation_target', newLang);
                  }}
                >
                  <option value="zho_Hans">Chinese (Simplified)</option>
                  <option value="zho_Hant">Chinese (Traditional)</option>
                  <option value="spa_Latn">Spanish</option>
                  <option value="fra_Latn">French</option>
                  <option value="deu_Latn">German</option>
                  <option value="jpn_Jpan">Japanese</option>
                  <option value="kor_Hang">Korean</option>
                </select>
              </div>
            </>
          )}

          <div className="form-group">
            <label className="form-group__label">Device</label>
            <select
              className="select"
              value={config.device}
              onChange={(e) => setConfig(prev => ({ ...prev, device: e.target.value }))}
            >
              <option value="auto">Auto (recommended)</option>
              <option value="cpu">CPU only</option>
              <option value="cuda">CUDA GPU</option>
            </select>
          </div>

          <div className="form-group">
            <label className="form-group__label">Audio Latency Target (ms)</label>
            <p className="form-group__description">
              Target latency for audio processing. Lower values provide faster response but may increase processing load. Recommended: 200ms.
            </p>
            <input
              type="number"
              className="select"
              value={latencyTarget}
              min={50}
              max={1000}
              step={50}
              onChange={(e) => {
                const newLatency = parseInt(e.target.value, 10);
                setLatencyTarget(newLatency);
                updatePersistentSetting('audio_latency_target_ms', newLatency);
              }}
            />
          </div>

          <button
            type="submit"
            className="btn btn-primary"
            disabled={isStarting || !config.asr_model_id}
            style={{ padding: '1rem 2rem', fontSize: '1rem' }}
          >
            {isStarting ? 'Starting...' : 'Start Session'}
          </button>
        </form>
      </div>
    </div>
  );
}