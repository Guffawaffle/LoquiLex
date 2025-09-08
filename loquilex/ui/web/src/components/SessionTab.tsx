import React, { useEffect, useMemo, useRef, useState } from 'react'
import { connectSessionWS } from '../ws'
import { api } from '../api'
import { useSessionStore } from '../store'
import VuMeter from './VuMeter'

export default function SessionTab({ sid }: { sid: string }) {
  const { sessions, appendFinal, setLive, removeSession } = useSessionStore(s => ({ sessions: s.sessions, appendFinal: s.appendFinal, setLive: s.setLive, removeSession: s.removeSession }))
  const s = sessions[sid]!
  const [vu, setVu] = useState({ rms: 0, peak: 0, clip_pct: 0 })
  const [status, setStatus] = useState<'open'|'closed'|'reconnecting'>('open')

  useEffect(() => {
    const stop = connectSessionWS(sid, (m) => {
      if (m.type === 'partial_en') setLive(sid, 'en', m.text)
      else if (m.type === 'partial_zh') setLive(sid, 'zh', m.text)
      else if (m.type === 'final_en') { appendFinal(sid, 'en', m.text, m.ts_server) ; setLive(sid, 'en', '') }
      else if (m.type === 'final_zh') { appendFinal(sid, 'zh', m.text, m.ts_server) ; setLive(sid, 'zh', '') }
      else if (m.type === 'vu') setVu({ rms: m.rms ?? 0, peak: m.peak ?? 0, clip_pct: m.clip_pct ?? 0 })
    }, async (st) => {
      setStatus(st)
      if (st === 'open') {
        try { await api.snapshot(sid) } catch {}
      }
    })
    return () => stop()
  }, [sid])

  const stopSession = async () => {
    try { await api.stopSession(sid) } catch {}
    removeSession(sid)
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-2">
        <span className="chip">ASR: {s.cfg.asr_model_id}</span>
        {s.cfg.mt_enabled && <span className="chip">MT: {s.cfg.mt_model_id} → {s.cfg.dest_lang}</span>}
        <span className="chip">Device: {s.cfg.device}</span>
        <span className="chip">VAD: {s.cfg.vad? 'on':'off'}</span>
        {status!=='open' && <span className="text-amber-600">{status==='reconnecting' ? 'Reconnecting…' : 'Disconnected'}</span>}
      </div>
      <div className="flex items-center gap-3">
        <VuMeter rms={vu.rms} peak={vu.peak} clipPct={vu.clip_pct} />
        <div className="text-sm">Clip {vu.clip_pct?.toFixed(1)}%</div>
      </div>

      <div className="grid grid-cols-2 gap-4">
        <div>
          <div className="text-xs uppercase text-slate-500">EN (live)</div>
          <div className="min-h-[2rem] p-2 rounded bg-slate-100 dark:bg-slate-800">{s.liveEn}</div>
          <div className="text-xs uppercase mt-3 text-slate-500">Finals</div>
          <div className="max-h-64 overflow-auto space-y-1 text-sm">
            {s.finals.filter(f => 'en' in f).map((f,i) => <div key={i}>• {(f as any).en}</div>)}
          </div>
        </div>
        <div>
          <div className="text-xs uppercase text-slate-500">ZH (live)</div>
          <div className="min-h-[2rem] p-2 rounded bg-slate-100 dark:bg-slate-800">{s.liveZh}</div>
          <div className="text-xs uppercase mt-3 text-slate-500">Finals</div>
          <div className="max-h-64 overflow-auto space-y-1 text-sm">
            {s.finals.filter(f => 'zh' in f).map((f,i) => <div key={i}>• {(f as any).zh}</div>)}
          </div>
        </div>
      </div>

      <div className="flex gap-2">
        <button className="px-3 py-2 rounded bg-slate-200 dark:bg-slate-800" onClick={()=>api.pause(sid)}>Pause</button>
        <button className="px-3 py-2 rounded bg-slate-200 dark:bg-slate-800" onClick={()=>api.resume(sid)}>Resume</button>
        <button className="px-3 py-2 rounded bg-slate-200 dark:bg-slate-800" onClick={()=>api.finalize(sid)}>Finalize now</button>
        <a className="px-3 py-2 rounded bg-slate-200 dark:bg-slate-800" href={`/out/${sid}/`} target="_blank">Open outputs</a>
        <button className="ml-auto px-3 py-2 rounded bg-red-600 text-white" onClick={stopSession}>Stop</button>
      </div>
    </div>
  )
}
