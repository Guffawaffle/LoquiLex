import React, { useEffect, useMemo, useState } from 'react'
import { api } from '../api'
import { AsrModel, MtModel, SessionCfg, RemoteModel } from '../types'
import { useSessionStore } from '../store'
import SearchCatalog from './SearchCatalog'
import ModelDetailsDrawer from './ModelDetailsDrawer'

type Props = { onStarted?: (sid: string) => void }

export default function LaunchWizard({ onStarted }: Props) {
  const { asr, mt, refreshModels, addSession } = useSessionStore(s => ({ asr: s.asr, mt: s.mt, refreshModels: s.refreshModels, addSession: s.addSession }))
  const [asrId, setAsrId] = useState('')
  const [mtEnabled, setMtEnabled] = useState(true)
  const [mtId, setMtId] = useState('')
  const [langs, setLangs] = useState<string[]>(['zho_Hans'])
  const [dest, setDest] = useState('zho_Hans')
  const [device, setDevice] = useState<'auto'|'cuda'|'cpu'>('auto')
  const [vad, setVad] = useState(true)
  const [beams, setBeams] = useState(1)
  const [seconds, setSeconds] = useState(1.5)
  const [testing, setTesting] = useState(false)
  const [testMsg, setTestMsg] = useState<string>('')
  const [starting, setStarting] = useState(false)
  const [activeTab, setActiveTab] = useState<'local' | 'search'>('local')
  const [selectedModel, setSelectedModel] = useState<RemoteModel | null>(null)
  const [detailsDrawerOpen, setDetailsDrawerOpen] = useState(false)
  const canStart = asrId.trim().length > 0 && (!mtEnabled || (mtId.trim().length>0 && dest))

  useEffect(() => { refreshModels().catch(()=>{}) }, [refreshModels])
  useEffect(() => { if (mtEnabled && mtId) { api.mtLangs(mtId).then(r => { setLangs(r.languages); if (!r.languages.includes(dest)) setDest(r.languages[0] || 'zho_Hans') }).catch(()=>{}) } }, [mtEnabled, mtId])

  const doSelfTest = async () => {
    setTesting(true); setTestMsg('')
    try {
      const r = await api.selfTest({ asr_model_id: asrId || undefined, device, seconds })
      setTestMsg(r.ok ? `OK: asr ${r.asr_load_ms}ms, rms ${r.rms_avg.toFixed(4)}, device ${r.effective_device || '?'} sr ${r.sample_rate ?? '?'} ` : `Failed: ${r.message}`)
    } catch (e:any) {
      setTestMsg(`Error: ${e.detail?.error || e.message}`)
    } finally { setTesting(false) }
  }

  const doStart = async () => {
    if (!canStart) return
    setStarting(true)
    const cfg: SessionCfg = { name: null as any, asr_model_id: asrId, mt_enabled: mtEnabled, mt_model_id: mtEnabled?mtId:undefined, dest_lang: dest, device, vad, beams, pause_flush_sec: 0.7, segment_max_sec: 7.0, partial_word_cap: 10, save_audio: 'off' }
    try {
      const r = await api.startSession(cfg)
      addSession(r.session_id, cfg)
      onStarted?.(r.session_id)
    } catch (e:any) {
      if (e.status === 409) {
        alert('CUDA session limit reached — switch Device to CPU or stop another CUDA session.')
      } else {
        alert(`Start failed: ${e.detail?.error || e.message}`)
      }
    } finally { setStarting(false) }
  }

  const handleModelSelect = (model: RemoteModel) => {
    // Set the selected model based on its task type
    if (model.task === 'asr') {
      setAsrId(model.id)
    } else if (model.task === 'mt') {
      setMtId(model.id)
      setMtEnabled(true)
    }
    // Switch back to local tab to show the selected model
    setActiveTab('local')
  }

  const handleShowDetails = (model: RemoteModel) => {
    setSelectedModel(model)
    setDetailsDrawerOpen(true)
  }

  return (
    <div className="max-w-5xl mx-auto space-y-6">
      {/* Tab Navigation */}
      <div className="flex gap-1 p-1 bg-slate-100 dark:bg-slate-800 rounded-lg">
        <button
          onClick={() => setActiveTab('local')}
          className={`flex-1 px-4 py-2 rounded-md text-sm font-medium transition-colors ${
            activeTab === 'local'
              ? 'bg-white dark:bg-slate-700 text-slate-900 dark:text-white shadow-sm'
              : 'text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white'
          }`}
        >
          Local Models
        </button>
        <button
          onClick={() => setActiveTab('search')}
          className={`flex-1 px-4 py-2 rounded-md text-sm font-medium transition-colors ${
            activeTab === 'search'
              ? 'bg-white dark:bg-slate-700 text-slate-900 dark:text-white shadow-sm'
              : 'text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white'
          }`}
        >
          Search Remote Catalogs
        </button>
      </div>

      {/* Tab Content */}
      {activeTab === 'local' && (
        <div className="space-y-4">
          <section className="space-y-2">
            <label className="block text-sm font-medium">ASR Model</label>
            <div className="flex gap-2">
              <select className="border p-2 rounded flex-1" value={asrId} onChange={e=>setAsrId(e.target.value)}>
                <option value="">Select…</option>
                {asr.map(m=> <option key={m.id} value={m.id}>{m.name}</option>)}
              </select>
              <input className="border p-2 rounded flex-1" placeholder="or type model id… (e.g., small.en)" value={asrId} onChange={e=>setAsrId(e.target.value)} />
            </div>
          </section>

          <section className="grid grid-cols-2 gap-4">
            <label className="flex items-center gap-2"><input type="checkbox" checked={mtEnabled} onChange={e=>setMtEnabled(e.target.checked)} /> Enable Translation</label>
            <div>
              <label className="block text-sm font-medium">Device</label>
              <select className="border p-2 rounded w-full" value={device} onChange={e=>setDevice(e.target.value as any)}>
                <option value="auto">auto</option>
                <option value="cuda">cuda</option>
                <option value="cpu">cpu</option>
              </select>
            </div>
            {mtEnabled && (
              <>
              <div>
                <label className="block text-sm font-medium">MT Model</label>
                <select className="border p-2 rounded w-full" value={mtId} onChange={e=>setMtId(e.target.value)}>
                  <option value="">Select…</option>
                  {mt.map(m=> <option key={m.id} value={m.id}>{m.name}</option>)}
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium">Destination language</label>
                <select className="border p-2 rounded w-full" value={dest} onChange={e=>setDest(e.target.value)}>
                  {langs.map(l=> <option key={l} value={l}>{l}</option>)}
                </select>
              </div>
              </>
            )}
          </section>

          <section className="grid grid-cols-3 gap-4">
            <label className="flex items-center gap-2"><input type="checkbox" checked={vad} onChange={e=>setVad(e.target.checked)} /> VAD</label>
            <div>
              <label className="block text-sm font-medium">Beam size</label>
              <input type="number" className="border p-2 rounded w-full" value={beams} min={1} max={8} onChange={e=>setBeams(parseInt(e.target.value||'1'))} />
            </div>
            <div>
              <label className="block text-sm font-medium">Self-test seconds</label>
              <input type="number" step="0.1" className="border p-2 rounded w-full" value={seconds} onChange={e=>setSeconds(parseFloat(e.target.value||'1.5'))} />
            </div>
          </section>

          <div className="flex gap-2 items-center">
            <button className="px-3 py-2 rounded bg-slate-200 dark:bg-slate-800" disabled={testing} onClick={doSelfTest}>{testing? 'Testing…':'Self-test'}</button>
            {testMsg && <span className="text-sm">{testMsg}</span>}
          </div>

          <div>
            <button className="px-4 py-2 rounded bg-blue-600 text-white disabled:opacity-50" disabled={!canStart || starting} onClick={doStart}>Start</button>
          </div>
        </div>
      )}

      {activeTab === 'search' && (
        <SearchCatalog 
          onModelSelect={handleModelSelect}
          onShowDetails={handleShowDetails}
        />
      )}

      {/* Model Details Drawer */}
      <ModelDetailsDrawer
        model={selectedModel}
        isOpen={detailsDrawerOpen}
        onClose={() => {
          setDetailsDrawerOpen(false)
          setSelectedModel(null)
        }}
        onSelect={(model) => {
          handleModelSelect(model)
          setDetailsDrawerOpen(false)
          setSelectedModel(null)
        }}
        onDownload={(model) => {
          // Handle download - could integrate with existing download API
          console.log('Download model:', model.id)
        }}
      />
    </div>
  )
}
