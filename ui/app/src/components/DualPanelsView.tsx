import { useState, useEffect, useRef, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { CaptionLine, SessionStatus } from '../types';
import { buildWsUrl } from '../utils/ws';
import { loadSettings } from '../utils/settings';

export function DualPanelsView() {
  const { sessionId } = useParams<{ sessionId: string }>();
  const navigate = useNavigate();
  const wsRef = useRef<WebSocket | null>(null);
  const [captions, setCaptions] = useState<CaptionLine[]>([]);
  const [status, setStatus] = useState<SessionStatus>({ status: 'idle' });
  const [showTimestamps, setShowTimestamps] = useState(() => {
    // Initialize from saved settings
    const settings = loadSettings();
    return settings.show_timestamps;
  });
  const [isPaused, setIsPaused] = useState(false);
  const captionsEndRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to bottom
  const scrollToBottom = useCallback(() => {
    captionsEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, []);

  useEffect(() => {
    scrollToBottom();
  }, [captions, scrollToBottom]);

  // WebSocket connection
  useEffect(() => {
    if (!sessionId) return;

  const wsUrl = buildWsUrl(sessionId);

    try {
      const ws = new WebSocket(wsUrl);
      wsRef.current = ws;

      ws.onopen = () => {
        console.log('WebSocket connected');
        setStatus(prev => ({ ...prev, status: 'running' }));
        // Send client hello
        ws.send(JSON.stringify({
          type: 'client_hello',
          data: { client_id: 'ui-app', version: '0.1.0' }
        }));
      };

      ws.onmessage = (event) => {
        try {
          const message = JSON.parse(event.data);
          handleWebSocketMessage(message);
        } catch (err) {
          console.error('Failed to parse WebSocket message:', err);
        }
      };

      ws.onclose = () => {
        console.log('WebSocket disconnected');
        setStatus(prev => ({ ...prev, status: 'reconnecting' }));
        // Attempt to reconnect after a delay
        setTimeout(() => {
          if (wsRef.current?.readyState === WebSocket.CLOSED) {
            // Reconnect logic would go here
          }
        }, 2000);
      };

      ws.onerror = (error) => {
        console.error('WebSocket error:', error);
        setStatus(prev => ({ ...prev, status: 'error' }));
      };

    } catch (err) {
      console.error('Failed to create WebSocket:', err);
      setStatus({ status: 'error' });
    }

    return () => {
      if (wsRef.current) {
        wsRef.current.close();
        wsRef.current = null;
      }
    };
  }, [sessionId]);

  const handleWebSocketMessage = (message: any) => {
    switch (message.type) {
      case 'asr_partial':
        handleASRPartial(message.data);
        break;
      case 'asr_final':
        handleASRFinal(message.data);
        break;
      case 'mt_final':
        handleMTFinal(message.data);
        break;
      case 'status':
        handleStatusUpdate(message.data);
        break;
      case 'metrics':
        handleMetricsUpdate(message.data);
        break;
      default:
        console.log('Unknown message type:', message.type);
    }
  };

  const handleASRPartial = (data: any) => {
    setCaptions(prev => {
      const existing = prev.find(c => c.id === `partial-${data.segment_id || 'current'}`);
      const line: CaptionLine = {
        id: `partial-${data.segment_id || 'current'}`,
        timestamp: data.timestamp,
        text: data.text || '',
        final: false,
      };

      if (existing) {
        return prev.map(c => c.id === line.id ? line : c);
      } else {
        return [...prev, line];
      }
    });
  };

  const handleASRFinal = (data: any) => {
    setCaptions(prev => {
      // Remove any partial with same segment_id and add final
      const filtered = prev.filter(c => c.id !== `partial-${data.segment_id || 'current'}`);
      const line: CaptionLine = {
        id: `final-${data.segment_id || Date.now()}`,
        timestamp: data.timestamp,
        text: data.text || '',
        final: true,
      };
      return [...filtered, line];
    });
  };

  const handleMTFinal = (data: any) => {
    setCaptions(prev =>
      prev.map(c =>
        c.id === `final-${data.segment_id}`
          ? { ...c, translation: data.translation }
          : c
      )
    );
  };

  const handleStatusUpdate = (data: any) => {
    setStatus(prev => ({ ...prev, ...data }));
  };

  const handleMetricsUpdate = (data: any) => {
    setStatus(prev => ({ ...prev, metrics: data }));
  };

  const togglePause = async () => {
    if (!sessionId) return;

    try {
      const endpoint = isPaused ? 'resume' : 'pause';
      const response = await fetch(`/sessions/${sessionId}/${endpoint}`, {
        method: 'POST',
      });

      if (response.ok) {
        setIsPaused(!isPaused);
      }
    } catch (err) {
      console.error(`Failed to ${isPaused ? 'resume' : 'pause'} session:`, err);
    }
  };

  const stopSession = async () => {
    if (!sessionId) return;

    try {
      await fetch(`/sessions/${sessionId}`, {
        method: 'DELETE',
      });
      navigate('/');
    } catch (err) {
      console.error('Failed to stop session:', err);
      // Navigate anyway
      navigate('/');
    }
  };

  const exportCaptions = (format: 'txt' | 'json' | 'vtt' | 'srt') => {
    const finalCaptions = captions.filter(c => c.final);

    let content = '';
    let filename = `captions-${sessionId}.${format}`;
    let mimeType = 'text/plain';

    switch (format) {
      case 'txt':
        content = finalCaptions.map(c => c.text).join('\n');
        break;
      case 'json':
        content = JSON.stringify(finalCaptions, null, 2);
        mimeType = 'application/json';
        break;
      case 'vtt':
        content = 'WEBVTT\n\n' + finalCaptions.map((c, i) => {
          if (!c.timestamp) return '';
          const start = formatTimestamp(c.timestamp);
          const end = formatTimestamp(c.timestamp + 3); // Assume 3s duration
          return `${i + 1}\n${start} --> ${end}\n${c.text}\n${c.translation || ''}\n`;
        }).join('\n');
        break;
      case 'srt':
        content = finalCaptions.map((c, i) => {
          if (!c.timestamp) return '';
          const start = formatSRTTimestamp(c.timestamp);
          const end = formatSRTTimestamp(c.timestamp + 3);
          return `${i + 1}\n${start} --> ${end}\n${c.text}\n${c.translation || ''}\n`;
        }).join('\n');
        break;
    }

    const blob = new Blob([content], { type: mimeType });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  const formatTimestamp = (seconds: number): string => {
    const date = new Date(seconds * 1000);
    return date.toISOString().substr(11, 12);
  };

  const formatSRTTimestamp = (seconds: number): string => {
    const date = new Date(seconds * 1000);
    return date.toISOString().substr(11, 12).replace('.', ',');
  };

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text).catch(err => {
      console.error('Failed to copy to clipboard:', err);
    });
  };

  // Keyboard shortcuts
  useEffect(() => {
    const handleKeyPress = (event: KeyboardEvent) => {
      if (event.ctrlKey || event.metaKey) {
        switch (event.key) {
          case 'e':
            event.preventDefault();
            exportCaptions('txt');
            break;
          case '.':
            event.preventDefault();
            togglePause();
            break;
        }
      } else {
        switch (event.key) {
          case 't':
          case 'T':
            setShowTimestamps(prev => !prev);
            break;
          case 's':
          case 'S':
            // Settings modal would open here
            break;
          case '?':
            // Help modal would open here
            break;
        }
      }
    };

    window.addEventListener('keydown', handleKeyPress);
    return () => window.removeEventListener('keydown', handleKeyPress);
  }, [isPaused]);

  return (
    <div className="dual-panels">
      <div className="dual-panels__header">
        <div className="dual-panels__title">
          LoquiLex Session
          <span className="text-muted" style={{ marginLeft: '0.5rem', fontSize: '0.875rem' }}>
            {sessionId}
          </span>
        </div>
        <div className="dual-panels__controls">
          <button
            className="btn"
            onClick={togglePause}
            title={`${isPaused ? 'Resume' : 'Pause'} (Ctrl/Cmd+.)`}
          >
            {isPaused ? '▶️' : '⏸️'}
          </button>
          <button
            className="btn"
            onClick={() => setShowTimestamps(!showTimestamps)}
            title="Toggle timestamps (T)"
          >
            🕐
          </button>
          <button className="btn" onClick={() => exportCaptions('txt')} title="Export as TXT (Ctrl/Cmd+E)">
            💾
          </button>
          <button className="btn btn-primary" onClick={stopSession}>
            Stop
          </button>
        </div>
      </div>

      <div className="dual-panels__content">
        <div className="caption-panel">
          <div className="caption-panel__header">
            <h3 className="caption-panel__title">Source Captions</h3>
          </div>
          <div className="caption-panel__content">
            {captions.map((caption) => (
              <div key={caption.id} className={`caption-line caption-line--${caption.final ? 'final' : 'partial'}`}>
                {showTimestamps && caption.timestamp && (
                  <div className="caption-line__timestamp">
                    {new Date(caption.timestamp * 1000).toLocaleTimeString()}
                  </div>
                )}
                <div className="caption-line__text">
                  {caption.text}
                </div>
                <div className="caption-line__actions">
                  <button
                    className="btn text-xs"
                    onClick={() => copyToClipboard(caption.text)}
                    title="Copy to clipboard"
                  >
                    📋
                  </button>
                </div>
              </div>
            ))}
            <div ref={captionsEndRef} />
          </div>
        </div>

        <div className="caption-panel">
          <div className="caption-panel__header">
            <h3 className="caption-panel__title">Translations</h3>
          </div>
          <div className="caption-panel__content">
            {captions.filter(c => c.translation).map((caption) => (
              <div key={`trans-${caption.id}`} className="caption-line caption-line--final">
                {showTimestamps && caption.timestamp && (
                  <div className="caption-line__timestamp">
                    {new Date(caption.timestamp * 1000).toLocaleTimeString()}
                  </div>
                )}
                <div className="caption-line__text">
                  {caption.translation}
                </div>
                <div className="caption-line__actions">
                  <button
                    className="btn text-xs"
                    onClick={() => copyToClipboard(caption.translation || '')}
                    title="Copy to clipboard"
                  >
                    📋
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* HUD */}
      <div className="hud">
        <div className="hud__title">Status</div>
        <div className="hud__metric">
          <span className="hud__label">Status:</span>
          <span className={`hud__value ${status.status === 'running' ? 'text-success' : status.status === 'error' ? 'text-error' : 'text-warning'}`}>
            {status.status}
          </span>
        </div>
        {status.device && (
          <div className="hud__metric">
            <span className="hud__label">Device:</span>
            <span className="hud__value">{status.device}</span>
          </div>
        )}
        {status.asr_model && (
          <div className="hud__metric">
            <span className="hud__label">ASR:</span>
            <span className="hud__value">{status.asr_model}</span>
          </div>
        )}
        {status.metrics && (
          <>
            {status.metrics.asr_partial_latency_p50 && (
              <div className="hud__metric">
                <span className="hud__label">ASR P50:</span>
                <span className="hud__value">{status.metrics.asr_partial_latency_p50.toFixed(0)}ms</span>
              </div>
            )}
            {status.metrics.queue_depth !== undefined && (
              <div className="hud__metric">
                <span className="hud__label">Queue:</span>
                <span className="hud__value">{status.metrics.queue_depth}</span>
              </div>
            )}
          </>
        )}

        <div style={{ marginTop: '1rem', fontSize: '0.75rem', color: 'var(--text-muted)' }}>
          Shortcuts: T=timestamps, Ctrl+E=export, Ctrl+.=pause
        </div>
      </div>
    </div>
  );
}