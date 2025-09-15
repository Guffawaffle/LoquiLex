import React, { useEffect } from 'react'
import { api } from './api'
import { DualPanelView } from './components/DualPanelView'
import { useWebSocketSession, useUIPreferences } from './hooks'
import { applyTheme } from './utils'

type Model = { id: string; name: string; source: string; quant?: string | null }

export default function App() {
  const { preferences, updatePreferences } = useUIPreferences()
  const [currentSessionId, setCurrentSessionId] = React.useState<string | null>(null)
  const [currentSessionName, setCurrentSessionName] = React.useState<string>('')
  const { sessionState } = useWebSocketSession(currentSessionId)
  
  // Apply theme changes
  useEffect(() => {
    applyTheme(preferences.theme)
  }, [preferences.theme])

  // Handle system theme changes
  useEffect(() => {
    if (preferences.theme === 'system') {
      const mediaQuery = window.matchMedia('(prefers-color-scheme: dark)')
      const handleChange = () => {
        applyTheme('system')
      }
      
      mediaQuery.addEventListener('change', handleChange)
      return () => {
        mediaQuery.removeEventListener('change', handleChange)
      }
    }
  }, [preferences.theme])

  // If we have an active session, show the dual panel view
  if (currentSessionId && sessionState) {
    return (
      <DualPanelView
        sessionState={sessionState}
        preferences={preferences}
        onPreferencesChange={updatePreferences}
      />
    )
  }

  // Otherwise, show the launch interface
  return <LaunchInterface onSessionCreated={setCurrentSessionId} onSessionNamed={setCurrentSessionName} />
}

// Launch interface for creating new sessions
function LaunchInterface({ 
  onSessionCreated, 
  onSessionNamed 
}: { 
  onSessionCreated: (id: string) => void
  onSessionNamed: (name: string) => void
}) {
  const [asr, setAsr] = React.useState<Model[]>([])
  const [mt, setMt] = React.useState<Model[]>([])
  const [form, setForm] = React.useState({
    name: 'Session',
    asr_model_id: '',
    mt_enabled: true,
    mt_model_id: '',
    dest_lang: 'zho_Hans',
    device: 'auto',
    vad: true,
    beams: 1,
  })
  const [testing, setTesting] = React.useState(false)
  const [testMsg, setTestMsg] = React.useState<string>('')
  
  const canStart = form.asr_model_id && (!form.mt_enabled || form.mt_model_id)

  React.useEffect(() => {
    api.getASRModels().then(setAsr).catch(() => setAsr([]))
    api.getMTModels().then(setMt).catch(() => setMt([]))
  }, [])

  const start = async () => {
    setTesting(true)
    setTestMsg('Running self-test…')
    try {
      const st = await api.selfTest(form.asr_model_id || undefined, form.device)
      if (!st.ok) {
        setTestMsg(`Self-test failed: ${st.message}`)
        setTesting(false)
        return
      }
      setTestMsg('Starting session…')
      const resp = await api.createSession(form)
      onSessionCreated(resp.session_id)
      onSessionNamed(form.name || 'Session')
    } catch (e: any) {
      setTestMsg(e?.message || 'Failed')
    } finally {
      setTesting(false)
    }
  }

  return (
    <div 
      className="min-h-screen p-8"
      style={{ 
        backgroundColor: 'var(--color-bg-primary)',
        color: 'var(--color-text-primary)'
      }}
    >
      <div className="max-w-2xl mx-auto space-y-6">
        <div className="text-center">
          <h1 className="text-3xl font-bold mb-2">LoquiLex — Realtime Bridge</h1>
          <p className="text-lg" style={{ color: 'var(--color-text-secondary)' }}>
            Configure and launch a new transcription session
          </p>
        </div>

        <div 
          className="p-6 rounded-lg space-y-4"
          style={{ backgroundColor: 'var(--color-bg-secondary)' }}
        >
          <div>
            <label className="block text-sm font-medium mb-1">Session Name</label>
            <input 
              className="w-full p-2 rounded border focus-visible:focus" 
              style={{
                backgroundColor: 'var(--color-bg-primary)',
                borderColor: 'var(--color-border)',
                color: 'var(--color-text-primary)'
              }}
              value={form.name} 
              onChange={e => setForm({ ...form, name: e.target.value })} 
            />
          </div>
          
          <div>
            <label className="block text-sm font-medium mb-1">ASR Model</label>
            <select 
              className="w-full p-2 rounded border focus-visible:focus" 
              style={{
                backgroundColor: 'var(--color-bg-primary)',
                borderColor: 'var(--color-border)',
                color: 'var(--color-text-primary)'
              }}
              value={form.asr_model_id} 
              onChange={e => setForm({ ...form, asr_model_id: e.target.value })}
            >
              <option value="">Select ASR model…</option>
              {asr.map(m => (
                <option key={m.id} value={m.id}>{m.name} ({m.source})</option>
              ))}
            </select>
          </div>
          
          <div className="flex items-center gap-2">
            <input 
              id="mt" 
              type="checkbox" 
              checked={form.mt_enabled} 
              onChange={e => setForm({ ...form, mt_enabled: e.target.checked })} 
            />
            <label htmlFor="mt" className="text-sm font-medium">Enable translation</label>
          </div>
          
          {form.mt_enabled && (
            <div>
              <label className="block text-sm font-medium mb-1">MT Model</label>
              <select 
                className="w-full p-2 rounded border focus-visible:focus" 
                style={{
                  backgroundColor: 'var(--color-bg-primary)',
                  borderColor: 'var(--color-border)',
                  color: 'var(--color-text-primary)'
                }}
                value={form.mt_model_id} 
                onChange={e => setForm({ ...form, mt_model_id: e.target.value })}
              >
                <option value="">Select MT model…</option>
                {mt.map(m => (
                  <option key={m.id} value={m.id}>{m.name}</option>
                ))}
              </select>
            </div>
          )}
          
          <div className="grid grid-cols-3 gap-4">
            <div>
              <label className="block text-sm font-medium mb-1">Device</label>
              <select 
                className="w-full p-2 rounded border focus-visible:focus" 
                style={{
                  backgroundColor: 'var(--color-bg-primary)',
                  borderColor: 'var(--color-border)',
                  color: 'var(--color-text-primary)'
                }}
                value={form.device} 
                onChange={e => setForm({ ...form, device: e.target.value })}
              >
                <option value="auto">auto</option>
                <option value="cuda">cuda</option>
                <option value="cpu">cpu</option>
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium mb-1">Beams</label>
              <input 
                type="number" 
                min={1} 
                className="w-full p-2 rounded border focus-visible:focus" 
                style={{
                  backgroundColor: 'var(--color-bg-primary)',
                  borderColor: 'var(--color-border)',
                  color: 'var(--color-text-primary)'
                }}
                value={form.beams} 
                onChange={e => setForm({ ...form, beams: Number(e.target.value) })} 
              />
            </div>
            <div className="flex items-center gap-2 mt-6">
              <input 
                id="vad" 
                type="checkbox" 
                checked={form.vad} 
                onChange={e => setForm({ ...form, vad: e.target.checked })} 
              />
              <label htmlFor="vad" className="text-sm font-medium">VAD</label>
            </div>
          </div>
          
          <div className="flex items-center gap-3 pt-4">
            <button 
              disabled={!canStart || testing} 
              onClick={start} 
              className="px-6 py-2 rounded-md font-medium transition-colors focus-visible:focus disabled:opacity-50"
              style={{
                backgroundColor: canStart && !testing ? 'var(--color-accent)' : 'var(--color-border)',
                color: canStart && !testing ? 'white' : 'var(--color-text-muted)'
              }}
            >
              {testing ? 'Testing…' : 'Start Session'}
            </button>
            {testMsg && (
              <span className="text-sm" style={{ color: 'var(--color-text-secondary)' }}>
                {testMsg}
              </span>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
