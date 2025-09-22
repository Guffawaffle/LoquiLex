import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { ASRModel, MTModel } from '../types';
import { AppSettings, loadSettings, saveSettings, clearSettings, DEFAULT_SETTINGS } from '../utils/settings';
import { SchemaForm } from './forms';
import { useSettingsSchema } from '../hooks/useSettingsSchema';

export function SchemaSettingsView() {
  const navigate = useNavigate();
  const { schema, loading: schemaLoading, error: schemaError } = useSettingsSchema();
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
      const updatedSettings = { ...loadedSettings };
      if (!updatedSettings.asr_model_id && asrData.length > 0) {
        updatedSettings.asr_model_id = asrData[0].id;
      }
      if (!updatedSettings.mt_model_id && mtData.length > 0) {
        updatedSettings.mt_model_id = mtData[0].id;
      }
      setSettings(updatedSettings);
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
      setTimeout(() => setSaved(false), 2000);
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

  const updateSetting = (key: string, value: any) => {
    setSettings(prev => ({ ...prev, [key]: value }));
    setSaved(false);
  };

  // Enhance schema with dynamic enum values for model selections
  const enhancedSchema = React.useMemo(() => {
    if (!schema) return null;

    const enhanced = { ...schema };
    
    // Add ASR model options
    if (enhanced.properties.asr_model_id && asrModels.length > 0) {
      enhanced.properties.asr_model_id = {
        ...enhanced.properties.asr_model_id,
        enum: asrModels.map(model => model.id)
      };
    }

    // Add MT model options  
    if (enhanced.properties.mt_model_id && mtModels.length > 0) {
      enhanced.properties.mt_model_id = {
        ...enhanced.properties.mt_model_id,
        enum: mtModels.map(model => model.id)
      };
    }

    return enhanced;
  }, [schema, asrModels, mtModels]);

  if (loading || schemaLoading) {
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

  if (schemaError) {
    return (
      <div className="settings-view">
        <div className="settings-view__container">
          <div className="settings-view__header">
            <h1 className="settings-view__title">Schema Error</h1>
            <p style={{ color: 'var(--error)' }}>{schemaError}</p>
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
          {enhancedSchema && (
            <SchemaForm
              schema={enhancedSchema}
              values={settings}
              onChange={updateSetting}
              level="basic"
            />
          )}

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