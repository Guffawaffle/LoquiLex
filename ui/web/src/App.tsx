import React, { useEffect, useMemo, useRef, useState } from 'react'
import { api } from './api'

type Model = { id: string; name: string; source: string; quant?: string | null }

type Session = {
  id: string
  name: string
  ws?: WebSocket
  log: string[]
  partial_en: string
  partial_zh: string
  finals_en: string[]
  finals_zh: string[]
  vu: { rms: number; peak: number }
}

function VuMeter({ vu }: { vu: { rms: number; peak: number } }) {
  const pct = Math.min(100, Math.round(vu.peak * 100))
  const rmsPct = Math.min(100, Math.round(vu.rms * 100))
  return (
    <div className="w-full h-3 bg-gray-200 rounded">
      <div className="h-3 bg-green-400 rounded" style={{ width: `${rmsPct}%` }} />
      <div className="-mt-3 h-3 bg-emerald-600/50 rounded" style={{ width: `${pct}%` }} />
    </div>
  )
}

function LaunchPane({ onLaunched }: { onLaunched: (sid: string, name: string) => void }) {
  const [asr, setAsr] = useState<Model[]>([])
  const [mt, setMt] = useState<Model[]>([])
  const [form, setForm] = useState({
    name: 'Session',
    asr_model_id: '',
    mt_enabled: true,
    mt_model_id: '',
    dest_lang: 'zho_Hans',
    device: 'auto',
    vad: true,
    beams: 1,
  })
  const canStart = form.asr_model_id && (!form.mt_enabled || form.mt_model_id)

  useEffect(() => {
    api.getASRModels().then(setAsr).catch(() => setAsr([]))
    api.getMTModels().then(setMt).catch(() => setMt([]))
  }, [])

  const start = async () => {
    const resp = await api.createSession(form)
    onLaunched(resp.session_id, form.name || 'Session')
  }

  return (
    <div className="space-y-4">
      <div>
        <label className="block text-sm">Name</label>
        <input className="border p-2 rounded w-full" value={form.name} onChange={e => setForm({ ...form, name: e.target.value })} />
      </div>
      <div>
        <label className="block text-sm">ASR model</label>
        <select className="border p-2 rounded w-full" value={form.asr_model_id} onChange={e => setForm({ ...form, asr_model_id: e.target.value })}>
          <option value="">Select…</option>
          {asr.map(m => (
            <option key={m.id} value={m.id}>{m.name} ({m.source})</option>
          ))}
        </select>
      </div>
      <div className="flex items-center gap-2">
        <input id="mt" type="checkbox" checked={form.mt_enabled} onChange={e => setForm({ ...form, mt_enabled: e.target.checked })} />
        <label htmlFor="mt">Enable translation</label>
      </div>
      {form.mt_enabled && (
        <div>
          <label className="block text-sm">MT model</label>
          <select className="border p-2 rounded w-full" value={form.mt_model_id} onChange={e => setForm({ ...form, mt_model_id: e.target.value })}>
            <option value="">Select…</option>
            {mt.map(m => (
              <option key={m.id} value={m.id}>{m.name}</option>
            ))}
          </select>
        </div>
      )}
      <div className="grid grid-cols-3 gap-4">
        <div>
          <label className="block text-sm">Device</label>
          <select className="border p-2 rounded w-full" value={form.device} onChange={e => setForm({ ...form, device: e.target.value })}>
            <option value="auto">auto</option>
            <option value="cuda">cuda</option>
            <option value="cpu">cpu</option>
          </select>
        </div>
        <div>
          <label className="block text-sm">Beams</label>
          <input type="number" min={1} className="border p-2 rounded w-full" value={form.beams} onChange={e => setForm({ ...form, beams: Number(e.target.value) })} />
        </div>
        <div className="flex items-center gap-2 mt-6">
          <input id="vad" type="checkbox" checked={form.vad} onChange={e => setForm({ ...form, vad: e.target.checked })} />
          <label htmlFor="vad">VAD</label>
        </div>
      </div>
      <button disabled={!canStart} onClick={start} className="px-4 py-2 rounded bg-blue-600 text-white disabled:opacity-50">Start</button>
    </div>
  )
}

function SessionTab({ s, onStop }: { s: Session; onStop: (sid: string) => void }) {
  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div className="font-semibold">{s.name}</div>
        <button className="text-red-600" onClick={() => onStop(s.id)}>Stop</button>
      </div>
      <VuMeter vu={s.vu} />
      <div className="grid grid-cols-2 gap-4">
        <div>
          <div className="text-sm text-gray-600">EN (partial)</div>
          <div className="p-2 border rounded h-20 overflow-auto">{s.partial_en}</div>
          <div className="text-sm text-gray-600 mt-2">EN (final)</div>
          <div className="p-2 border rounded h-28 overflow-auto whitespace-pre-wrap">{s.finals_en.join('\n')}</div>
        </div>
        <div>
          <div className="text-sm text-gray-600">ZH (partial)</div>
          <div className="p-2 border rounded h-20 overflow-auto">{s.partial_zh}</div>
          <div className="text-sm text-gray-600 mt-2">ZH (final)</div>
          <div className="p-2 border rounded h-28 overflow-auto whitespace-pre-wrap">{s.finals_zh.join('\n')}</div>
        </div>
      </div>
      <div>
        <div className="text-sm text-gray-600">Events</div>
        <div className="p-2 border rounded h-32 overflow-auto text-xs font-mono whitespace-pre-wrap">{s.log.join('\n')}</div>
      </div>
    </div>
  )
}

export default function App() {
  const [tab, setTab] = useState<'launch' | 'sessions' | 'settings'>('launch')
  const [sessions, setSessions] = useState<Session[]>([])

  const addSession = (sid: string, name: string) => {
    const ws = new WebSocket(`ws://localhost:8000/events/${sid}`)
    const s: Session = { id: sid, name, ws, log: [], partial_en: '', partial_zh: '', finals_en: [], finals_zh: [], vu: { rms: 0, peak: 0 } }
    ws.onmessage = (ev) => {
      try {
        const m = JSON.parse(ev.data)
        setSessions(prev => prev.map(x => {
          if (x.id !== sid) return x
          const log = x.log.concat([JSON.stringify(m)])
          if (log.length > 200) log.shift()
          if (m.type === 'partial_en') return { ...x, partial_en: m.text, log }
          if (m.type === 'partial_zh') return { ...x, partial_zh: m.text, log }
          if (m.type === 'final_en') return { ...x, finals_en: x.finals_en.concat([m.text]).slice(-200), partial_en: '', log }
          if (m.type === 'final_zh') return { ...x, finals_zh: x.finals_zh.concat([m.text]).slice(-200), partial_zh: '', log }
          if (m.type === 'vu') return { ...x, vu: { rms: m.rms, peak: m.peak }, log }
          return { ...x, log }
        }))
      } catch {}
    }
    setSessions(prev => prev.concat([s]))
    setTab('sessions')
  }

  const stop = async (sid: string) => {
    try { await api.stopSession(sid) } catch {}
    setSessions(prev => prev.filter(s => s.id !== sid))
  }

  return (
    <div className="max-w-5xl mx-auto p-4 space-y-4">
      <div className="flex items-center gap-4">
        <button className={`px-3 py-1 rounded ${tab==='launch'?'bg-blue-600 text-white':'bg-gray-100'}`} onClick={() => setTab('launch')}>Launch</button>
        <button className={`px-3 py-1 rounded ${tab==='sessions'?'bg-blue-600 text-white':'bg-gray-100'}`} onClick={() => setTab('sessions')}>Sessions ({sessions.length})</button>
        <button className={`px-3 py-1 rounded ${tab==='settings'?'bg-blue-600 text-white':'bg-gray-100'}`} onClick={() => setTab('settings')}>Settings</button>
      </div>
      {tab === 'launch' && <LaunchPane onLaunched={addSession} />}
      {tab === 'sessions' && (
        sessions.length === 0 ? <div className="text-gray-600">No sessions yet.</div> :
        <div className="space-y-4">
          {sessions.map(s => (
            <div key={s.id} className="border rounded p-3"><SessionTab s={s} onStop={stop} /></div>
          ))}
        </div>
      )}
      {tab === 'settings' && (
        <div className="text-gray-600">Model management and profiles (coming next).</div>
      )}
    </div>
  )
}
