import { create } from 'zustand'
import { AsrModel, MtModel, SessionCfg } from './types'
import { api } from './api'

type SessionState = {
  cfg: SessionCfg
  liveEn: string
  liveZh: string
  finals: { en?: string; zh?: string; ts?: number }[]
}

export type Store = {
  asr: AsrModel[]
  mt: MtModel[]
  sessions: Record<string, SessionState>
  setAsr: (m: AsrModel[]) => void
  setMt: (m: MtModel[]) => void
  addSession: (sid: string, cfg: SessionCfg) => void
  removeSession: (sid: string) => void
  appendFinal: (sid: string, kind: 'en'|'zh', text: string, ts?: number) => void
  setLive: (sid: string, kind: 'en'|'zh', text: string) => void
  updateCfg: (sid: string, cfg: Partial<SessionCfg>) => void
  refreshModels: () => Promise<void>
}

type SetFn = (partial: Partial<Store> | ((state: Store) => Partial<Store>)) => void
export const useSessionStore = create<Store>((set: SetFn, get: () => Store) => ({
  asr: [],
  mt: [],
  sessions: {},
  setAsr: (m: AsrModel[]) => set(() => ({ asr: m })),
  setMt: (m: MtModel[]) => set(() => ({ mt: m })),
  addSession: (sid: string, cfg: SessionCfg) => set((s) => ({ sessions: { ...s.sessions, [sid]: { cfg, liveEn: '', liveZh: '', finals: [] } } })),
  removeSession: (sid: string) => set((s) => { const n = { ...s.sessions }; delete n[sid]; return { sessions: n } }),
  appendFinal: (sid: string, kind: 'en'|'zh', text: string, ts?: number) => set((s) => {
    const cur = s.sessions[sid]; if (!cur) return {}
    const finals = cur.finals.concat([{ [kind]: text, ts }] as any)
    if (finals.length > 200) finals.shift()
    return { sessions: { ...s.sessions, [sid]: { ...cur, finals } } }
  }),
  setLive: (sid: string, kind: 'en'|'zh', text: string) => set((s) => {
    const cur = s.sessions[sid]; if (!cur) return {}
    const next = { ...cur, liveEn: kind==='en'?text:cur.liveEn, liveZh: kind==='zh'?text:cur.liveZh }
    return { sessions: { ...s.sessions, [sid]: next } }
  }),
  updateCfg: (sid: string, cfg: Partial<SessionCfg>) => set((s) => {
    const cur = s.sessions[sid]; if (!cur) return {}
    return { sessions: { ...s.sessions, [sid]: { ...cur, cfg: { ...cur.cfg, ...cfg } } } }
  }),
  async refreshModels() {
    const [asr, mt] = await Promise.all([api.listAsr(), api.listMt()])
    set(() => ({ asr, mt }))
  }
}))
