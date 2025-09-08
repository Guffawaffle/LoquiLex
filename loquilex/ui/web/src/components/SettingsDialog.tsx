import React, { useEffect, useState } from 'react'
import { api } from '../api'
import { connectDownloadWS } from '../ws'
import { useSessionStore } from '../store'

export default function SettingsDialog() {
  const { refreshModels } = useSessionStore(s => ({ refreshModels: s.refreshModels }))
  const [profiles, setProfiles] = useState<string[]>([])
  const [selected, setSelected] = useState('')
  const [downloadRepo, setDownloadRepo] = useState('')
  const [downloadJob, setDownloadJob] = useState<string | null>(null)
  const [downloadPct, setDownloadPct] = useState<number | null>(null)

  const load = async () => setProfiles(await api.profiles.list())
  useEffect(() => { load().catch(()=>{}) }, [])

  const startDownload = async () => {
    if (!downloadRepo) return
    const r = await api.download.start(downloadRepo, 'asr')
    setDownloadJob(r.job_id)
    const stop = connectDownloadWS(r.job_id, (m) => {
      if (m.type === 'download_progress') setDownloadPct(m.pct)
      if (m.type === 'download_done') { setDownloadPct(100); stop(); refreshModels() }
      if (m.type === 'download_error') { alert(`Download error: ${m.message}`); stop() }
    })
  }

  const cancelDownload = async () => { if (downloadJob) { await api.download.cancel(downloadJob); setDownloadJob(null); setDownloadPct(null) } }

  const restoreDefaults = () => { localStorage.removeItem('launch.form'); alert('Defaults restored (local)') }

  const saveProfile = async () => {
    const name = prompt('Profile name?')?.trim(); if (!name) return
    const body = JSON.parse(localStorage.getItem('launch.form') || '{}')
    await api.profiles.save(name, body)
    setSelected(name)
    load()
  }

  const loadProfile = async () => {
    if (!selected) return
    const body = await api.profiles.get(selected)
    localStorage.setItem('launch.form', JSON.stringify(body))
    alert('Profile loaded into launch form')
  }

  const deleteProfile = async () => {
    if (!selected) return
    await api.profiles.del(selected)
    setSelected('')
    load()
  }

  return (
    <div className="max-w-3xl space-y-6">
      <section>
        <h2 className="font-semibold mb-2">Profiles</h2>
        <div className="flex gap-2 items-center">
          <select className="border p-2 rounded" value={selected} onChange={e=>setSelected(e.target.value)}>
            <option value="">Select…</option>
            {profiles.map(p => <option key={p} value={p}>{p}</option>)}
          </select>
          <button className="px-3 py-2 rounded bg-slate-200 dark:bg-slate-800" onClick={loadProfile}>Load</button>
          <button className="px-3 py-2 rounded bg-slate-200 dark:bg-slate-800" onClick={saveProfile}>Save current as…</button>
          <button className="px-3 py-2 rounded bg-slate-200 dark:bg-slate-800" onClick={deleteProfile}>Delete</button>
        </div>
      </section>
      <section>
        <h2 className="font-semibold mb-2">Model Management</h2>
        <div className="flex gap-2 items-center">
          <input className="border p-2 rounded flex-1" placeholder="repo id (e.g., openai/whisper-small.en)" value={downloadRepo} onChange={e=>setDownloadRepo(e.target.value)} />
          <button className="px-3 py-2 rounded bg-slate-200 dark:bg-slate-800" onClick={startDownload}>Download…</button>
          {downloadPct!=null && <span className="text-sm">{downloadPct}%</span>}
          {downloadJob && <button className="px-3 py-2 rounded bg-slate-200 dark:bg-slate-800" onClick={cancelDownload}>Cancel</button>}
          <button className="px-3 py-2 rounded bg-slate-200 dark:bg-slate-800" onClick={()=>refreshModels()}>Refresh local models</button>
        </div>
      </section>
      <section>
        <h2 className="font-semibold mb-2">Defaults</h2>
        <button className="px-3 py-2 rounded bg-slate-200 dark:bg-slate-800" onClick={restoreDefaults}>Restore defaults</button>
        <div className="text-sm mt-2">CORS note: ensure backend allows http://localhost:5173 via LX_ALLOWED_ORIGINS.</div>
      </section>
    </div>
  )
}
