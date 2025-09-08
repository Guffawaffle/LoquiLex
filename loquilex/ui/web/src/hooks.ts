import { useEffect } from 'react'
import { connectSessionWS } from './ws'
import { api } from './api'
import { useSessionStore } from './store'

export function useSessionConnection(sid: string) {
  const updateCfg = useSessionStore(s => s.updateCfg)
  useEffect(() => {
    const stop = connectSessionWS(sid, () => {}, async (st) => {
      if (st === 'open') {
        try {
          const snap = await api.snapshot(sid)
          if (snap && snap.cfg) updateCfg(sid, snap.cfg)
        } catch {}
      }
    })
    return () => stop()
  }, [sid, updateCfg])
}
