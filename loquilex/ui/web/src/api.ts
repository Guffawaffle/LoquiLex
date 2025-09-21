import { AsrModel, MtModel, SelfTestResp, SessionCfg, RemoteModel, SearchFilters, SearchResult } from './types'

async function j<T>(p: Promise<Response>): Promise<T> {
  const r = await p
  if (!r.ok) {
    let detail: any
    try { detail = await r.json() } catch { detail = await r.text() }
    const e: any = new Error(`HTTP ${r.status}`)
    e.status = r.status
    e.detail = detail
    throw e
  }
  return r.json() as Promise<T>
}

export const api = {
  listAsr: (): Promise<AsrModel[]> => j(fetch('/models/asr')),
  listMt: (): Promise<MtModel[]> => j(fetch('/models/mt')),
  mtLangs: (modelId: string): Promise<{ model_id: string; languages: string[] }> => j(fetch(`/languages/mt/${encodeURIComponent(modelId)}`)),
  selfTest: (body: { asr_model_id?: string | null; device: 'auto'|'cuda'|'cpu'; seconds?: number }): Promise<SelfTestResp> => j(fetch('/sessions/selftest', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) })),
  startSession: (cfg: SessionCfg): Promise<{ session_id: string }> => j(fetch('/sessions', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(cfg) })),
  stopSession: (sid: string): Promise<{ stopped: boolean }> => j(fetch(`/sessions/${sid}`, { method: 'DELETE' })),
  pause: (sid: string) => j(fetch(`/sessions/${sid}/pause`, { method: 'POST' })),
  resume: (sid: string) => j(fetch(`/sessions/${sid}/resume`, { method: 'POST' })),
  finalize: (sid: string) => j(fetch(`/sessions/${sid}/finalize`, { method: 'POST' })),
  snapshot: (sid: string): Promise<{ sid: string; cfg: any; status: string }> => j(fetch(`/sessions/${sid}/snapshot`)),
  profiles: {
    list: (): Promise<string[]> => j(fetch('/profiles')),
    get: (name: string): Promise<any> => j(fetch(`/profiles/${encodeURIComponent(name)}`)),
    save: (name: string, body: any): Promise<{ ok: boolean }> => j(fetch(`/profiles/${encodeURIComponent(name)}` , { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) })),
    del: (name: string): Promise<{ ok: boolean }> => j(fetch(`/profiles/${encodeURIComponent(name)}`, { method: 'DELETE' }))
  },
  download: {
    start: (repo_id: string, type: string): Promise<{ job_id: string; status: string }> => j(fetch('/models/download', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ repo_id, type }) })),
    cancel: (job_id: string): Promise<{ cancelled: boolean }> => j(fetch(`/models/download/${job_id}`, { method: 'DELETE' }))
  },
  search: {
    models: (filters: SearchFilters, page = 1, per_page = 20): Promise<SearchResult> => {
      const params = new URLSearchParams({
        page: page.toString(),
        per_page: per_page.toString(),
        ...Object.fromEntries(
          Object.entries(filters).filter(([, v]) => v !== undefined).map(([k, v]) => [k, String(v)])
        )
      })
      return j(fetch(`/models/search?${params}`))
    },
    model: (modelId: string): Promise<RemoteModel> => j(fetch(`/models/remote/${encodeURIComponent(modelId)}`))
  }
}
