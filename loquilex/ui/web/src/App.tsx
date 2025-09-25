import React, { useMemo, useState } from 'react'
import LaunchWizard from './components/LaunchWizard'
import SettingsDialog from './components/SettingsDialog'
import SessionTab from './components/SessionTab'
import DownloadsPage from './components/DownloadsPage'
import { useSessionStore } from './store'

type TabKey = 'launch' | 'downloads' | 'settings' | { sid: string }

export default function App() {
  const sessions = useSessionStore(s => s.sessions)
  const [active, setActive] = useState<TabKey>('launch')

  const sessionTabs = useMemo(() => Object.keys(sessions), [sessions])

  return (
    <div className="min-h-screen flex flex-col">
      <header className="border-b border-slate-200 dark:border-slate-800 p-3 flex items-center gap-3">
        <h1 className="text-lg font-semibold">LoquiLex</h1>
        <nav className="flex gap-2">
          <button className={`px-3 py-1 rounded ${active==='launch'?'bg-blue-600 text-white':'bg-slate-200 dark:bg-slate-800'}`} onClick={()=>setActive('launch')}>Launch</button>
          {sessionTabs.map(sid=> (
            <button key={sid} className={`px-3 py-1 rounded ${typeof active==='object' && active.sid===sid ? 'bg-blue-600 text-white':'bg-slate-200 dark:bg-slate-800'}`} onClick={()=>setActive({sid})}>Session {sid.slice(0,6)}</button>
          ))}
          <button className={`px-3 py-1 rounded ${active==='downloads'?'bg-blue-600 text-white':'bg-slate-200 dark:bg-slate-800'}`} onClick={()=>setActive('downloads')}>Downloads</button>
          <button className={`px-3 py-1 rounded ${active==='settings'?'bg-blue-600 text-white':'bg-slate-200 dark:bg-slate-800'}`} onClick={()=>setActive('settings')}>Settings</button>
        </nav>
      </header>
      <main className="flex-1 p-4">
        {active==='launch' && <LaunchWizard onStarted={(sid)=> setActive({sid})} />}
        {active==='downloads' && <DownloadsPage />}
        {active==='settings' && <SettingsDialog />}
        {typeof active==='object' && sessions[active.sid] && (
          <SessionTab sid={active.sid} />
        )}
      </main>
    </div>
  )
}
