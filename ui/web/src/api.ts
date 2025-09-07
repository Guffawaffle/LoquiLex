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
  }
}
