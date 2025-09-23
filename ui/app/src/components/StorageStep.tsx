import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { StorageInfo, BaseDirectoryValidation } from '../types';
import { loadSettings, saveSettings, AppSettings } from '../utils/settings';

export function StorageStep() {
  const navigate = useNavigate();
  const [settings, setSettings] = useState<AppSettings>(() => loadSettings());
  const [storageInfo, setStorageInfo] = useState<StorageInfo | null>(null);
  const [customPath, setCustomPath] = useState('');
  const [validation, setValidation] = useState<BaseDirectoryValidation | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    loadStorageInfo();
  }, []);

  const loadStorageInfo = async () => {
    try {
      setLoading(true);
      const response = await fetch(`/storage/info?path=${encodeURIComponent(settings.base_directory)}`);
      if (!response.ok) {
        throw new Error('Failed to load storage information');
      }
      const data = await response.json();
      setStorageInfo(data);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load storage info');
    } finally {
      setLoading(false);
    }
  };

  const validatePath = async (path: string) => {
    try {
      setLoading(true);
      const response = await fetch('/storage/base-directory', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ path }),
      });
      
      if (!response.ok) {
        throw new Error('Failed to validate path');
      }
      
      const data = await response.json();
      setValidation(data);
      
      if (data.valid) {
        const updatedSettings = { ...settings, base_directory: data.path };
        setSettings(updatedSettings);
        saveSettings(updatedSettings);
        await loadStorageInfo(); // Refresh storage info for new path
      }
      
      return data.valid;
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to validate path');
      return false;
    } finally {
      setLoading(false);
    }
  };

  const handleCustomPathSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!customPath.trim()) return;
    
    await validatePath(customPath.trim());
    setCustomPath('');
  };

  const handleContinue = () => {
    // Navigate to the model selection view
    navigate('/models');
  };

  const formatBytes = (bytes: number) => {
    const units = ['B', 'KB', 'MB', 'GB', 'TB'];
    let size = bytes;
    let unitIndex = 0;
    
    while (size >= 1024 && unitIndex < units.length - 1) {
      size /= 1024;
      unitIndex++;
    }
    
    return `${size.toFixed(unitIndex > 0 ? 1 : 0)} ${units[unitIndex]}`;
  };

  const getStorageStatusColor = (percentUsed: number) => {
    if (percentUsed >= 90) return 'text-red-600';
    if (percentUsed >= 75) return 'text-yellow-600';
    return 'text-green-600';
  };

  return (
    <div className="storage-step">
      <div className="storage-step__container">
        <div className="storage-step__header">
          <h1 className="storage-step__title">Storage Setup</h1>
          <p className="storage-step__subtitle">
            Configure where LoquiLex will store your session outputs and transcriptions.
          </p>
        </div>

        {error && (
          <div className="p-4" style={{ background: 'var(--error)', color: 'white', borderRadius: '4px', marginBottom: '1rem' }}>
            {error}
          </div>
        )}

        <div className="storage-step__content">
          <section className="form-group">
            <label className="form-group__label">Current Storage Location</label>
            <div className="storage-info-card">
              <div className="storage-info-card__path">
                <strong>Path:</strong> {storageInfo?.path || settings.base_directory}
              </div>
              
              {storageInfo && (
                <>
                  <div className="storage-info-card__stats">
                    <div className="storage-stat">
                      <span className="storage-stat__label">Total Space:</span>
                      <span className="storage-stat__value">{formatBytes(storageInfo.total_bytes)}</span>
                    </div>
                    <div className="storage-stat">
                      <span className="storage-stat__label">Free Space:</span>
                      <span className="storage-stat__value">{formatBytes(storageInfo.free_bytes)}</span>
                    </div>
                    <div className="storage-stat">
                      <span className="storage-stat__label">Used:</span>
                      <span className={`storage-stat__value ${getStorageStatusColor(storageInfo.percent_used)}`}>
                        {storageInfo.percent_used.toFixed(1)}%
                      </span>
                    </div>
                  </div>
                  
                  <div className="storage-progress">
                    <div className="storage-progress__bar">
                      <div 
                        className="storage-progress__fill"
                        style={{ 
                          width: `${storageInfo.percent_used}%`,
                          backgroundColor: storageInfo.percent_used >= 90 ? '#ef4444' : 
                                         storageInfo.percent_used >= 75 ? '#f59e0b' : '#10b981'
                        }}
                      />
                    </div>
                  </div>
                  
                  <div className="storage-info-card__status">
                    <span className={`status-indicator ${storageInfo.writable ? 'status-indicator--success' : 'status-indicator--error'}`}>
                      {storageInfo.writable ? '✓ Writable' : '✗ Not writable'}
                    </span>
                  </div>
                </>
              )}
            </div>
          </section>

          <section className="form-group">
            <label className="form-group__label">Change Storage Location</label>
            <p className="form-group__description">
              Enter a custom path to store your transcription outputs. The directory will be created if it doesn't exist.
            </p>
            
            <form className="flex gap-2" onSubmit={handleCustomPathSubmit}>
              <input
                type="text"
                className="input flex-1"
                placeholder="/path/to/storage/directory"
                value={customPath}
                onChange={(e) => setCustomPath(e.target.value)}
                disabled={loading}
              />
              <button
                type="submit"
                className="btn btn-secondary"
                disabled={loading || !customPath.trim()}
              >
                {loading ? 'Validating...' : 'Set Path'}
              </button>
            </form>
            
            {validation && (
              <div
                className="mt-2 p-3 rounded"
                style={{
                  background: validation.valid ? 'var(--success-bg)' : 'var(--error-bg)',
                  color: validation.valid ? 'var(--success-text)' : 'var(--error-text)',
                }}
              >
                {validation.message}
              </div>
            )}
          </section>

          <section className="form-group">
            <h3 className="form-group__label">Storage Requirements</h3>
            <ul className="text-sm text-gray-600 space-y-1">
              <li>• Minimum 1GB free space recommended</li>
              <li>• Directory must be writable</li>
              <li>• Audio files (if enabled) require additional space</li>
              <li>• Transcription files are typically small (~1KB per minute)</li>
            </ul>
          </section>

          <div className="storage-step__actions">
            <button
              type="button"
              className="btn btn-primary"
              onClick={handleContinue}
              disabled={loading || (storageInfo ? !storageInfo.writable : false)}
            >
              Continue to Model Selection
            </button>
            
            <button
              type="button"
              className="btn btn-secondary"
              onClick={loadStorageInfo}
              disabled={loading}
            >
              {loading ? 'Refreshing...' : 'Refresh Storage Info'}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}