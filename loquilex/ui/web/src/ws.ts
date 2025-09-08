import { DownloadMsg, EventMsg } from './types'

export function connectSessionWS(sid: string, onMsg: (m: EventMsg) => void, onStatus?: (s: 'open'|'closed'|'reconnecting') => void) {
  let ws: WebSocket | null = null
  let stopped = false
  let backoff = 500

  const url = (() => {
    const proto = location.protocol === 'https:' ? 'wss' : 'ws'
    return `${proto}://${location.host}/events/${encodeURIComponent(sid)}`
  })()

  const open = () => {
    if (stopped) return
    try {
      ws = new WebSocket(url)
    } catch {
      scheduleReconnect()
      return
    }
    ws.onopen = () => {
      backoff = 500
      onStatus?.('open')
    }
    ws.onmessage = ev => {
      try {
        const msg = JSON.parse(ev.data) as EventMsg
        onMsg(msg)
      } catch {}
    }
    ws.onclose = () => {
      onStatus?.('closed')
      scheduleReconnect()
    }
    ws.onerror = () => {
      try { ws?.close() } catch {}
    }
  }

  const scheduleReconnect = () => {
    if (stopped) return
    onStatus?.('reconnecting')
    const delay = Math.min(8000, backoff)
    backoff = Math.min(8000, backoff * 2)
    setTimeout(open, delay)
  }

  open()

  return () => {
    stopped = true
    try { ws?.close() } catch {}
  }
}

export function connectDownloadWS(jobId: string, onMsg: (m: DownloadMsg) => void) {
  const proto = location.protocol === 'https:' ? 'wss' : 'ws'
  const url = `${proto}://${location.host}/events/_download/${encodeURIComponent(jobId)}`
  const ws = new WebSocket(url)
  ws.onmessage = ev => {
    try {
      onMsg(JSON.parse(ev.data) as DownloadMsg)
    } catch {}
  }
  return () => { try { ws.close() } catch {} }
}
