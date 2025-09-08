export const api = {
  async getASRModels() {
    const r = await fetch('/models/asr')
    if (!r.ok) throw new Error('Failed')
    return r.json()
  },
  async getMTModels() {
    const r = await fetch('/models/mt')
    if (!r.ok) throw new Error('Failed')
    return r.json()
  },
  async createSession(cfg: any) {
    const r = await fetch('/sessions', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(cfg) })
    if (!r.ok) throw new Error('Failed to create')
    return r.json()
  },
  async stopSession(sid: string) {
    const r = await fetch(`/sessions/${sid}`, { method: 'DELETE' })
    if (!r.ok) throw new Error('Failed to stop')
    return r.json()
  },
  async selfTest(asr_model_id?: string, device: string = 'auto', seconds = 1.5) {
    const r = await fetch('/sessions/selftest', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ asr_model_id, device, seconds })})
    if (!r.ok) throw new Error('Self-test failed')
    return r.json()
  },
  async startDownload(repo_id: string, type: string) {
    const r = await fetch('/models/download', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ repo_id, type }) })
    if (!r.ok) throw new Error('Failed to start download')
    return r.json() as Promise<{ job_id: string }>
  },
  async cancelDownload(job_id: string) {
    const r = await fetch(`/models/download/${job_id}`, { method: 'DELETE' })
    if (!r.ok) throw new Error('Failed to cancel')
    return r.json()
  },
  async listProfiles(): Promise<string[]> {
    const r = await fetch('/profiles')
    if (!r.ok) throw new Error('Failed to list profiles')
    return r.json()
  },
  async getProfile(name: string) {
    const r = await fetch(`/profiles/${encodeURIComponent(name)}`)
    if (!r.ok) throw new Error('Failed to load profile')
    return r.json()
  },
  async saveProfile(name: string, data: any) {
    const r = await fetch(`/profiles/${encodeURIComponent(name)}`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(data) })
    if (!r.ok) throw new Error('Failed to save profile')
    return r.json()
  },
  async deleteProfile(name: string) {
    const r = await fetch(`/profiles/${encodeURIComponent(name)}`, { method: 'DELETE' })
    if (!r.ok) throw new Error('Failed to delete profile')
    return r.json()
  }
}
