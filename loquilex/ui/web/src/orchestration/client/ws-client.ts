/**
 * WebSocket Client Wrapper
 * 
 * Provides a robust WebSocket client with automatic reconnection,
 * backpressure handling, and typed message support.
 */

import type { 
  WSEnvelope, 
  MessageType, 
  ConnectionState, 
  CancellationToken 
} from '../types'
import { createCancellationToken } from '../utils/cancellation'
import { withRetry, DEFAULT_RETRY_CONFIG } from '../utils/retry'
import { MessageBuffer } from '../utils/bounded-queue'

export interface WSClientConfig {
  url: string
  reconnect: boolean
  maxReconnectAttempts: number
  reconnectDelay: number
  maxReconnectDelay: number
  heartbeatInterval?: number
  maxMessageSize?: number
  maxBufferSize?: number
}

export interface WSClientEvents {
  onStateChange?: (state: ConnectionState) => void
  onMessage?: <T = unknown>(envelope: WSEnvelope<T>) => void
  onError?: (error: Error) => void
  onConnect?: () => void
  onDisconnect?: (reason: string) => void
}

export class WSClient {
  private config: WSClientConfig
  private events: WSClientEvents
  private ws: WebSocket | null = null
  private state: ConnectionState = 'disconnected'
  private reconnectAttempt = 0
  private reconnectTimer: number | null = null
  private heartbeatTimer: number | null = null
  private messageBuffer: MessageBuffer<WSEnvelope>
  private cancellationToken: CancellationToken
  private lastSeq = 0

  constructor(config: WSClientConfig, events: WSClientEvents = {}) {
    this.config = {
      reconnect: true,
      maxReconnectAttempts: 10,
      reconnectDelay: 1000,
      maxReconnectDelay: 30000,
      heartbeatInterval: 30000,
      maxMessageSize: 64 * 1024,
      maxBufferSize: 1024 * 1024,
      ...config
    }
    this.events = events
    this.cancellationToken = createCancellationToken()
    
    this.messageBuffer = new MessageBuffer({
      maxSize: 1000,
      maxBytes: this.config.maxBufferSize,
      dropStrategy: 'oldest',
      onDrop: (dropped) => {
        console.warn('Dropped buffered message due to overflow:', dropped)
      }
    })
  }

  /**
   * Connect to the WebSocket server
   */
  async connect(): Promise<void> {
    if (this.state === 'connected' || this.state === 'connecting') {
      return
    }

    this.setState('connecting')
    this.reconnectAttempt = 0

    return withRetry(
      () => this.attemptConnection(),
      {
        ...DEFAULT_RETRY_CONFIG,
        maxAttempts: this.config.maxReconnectAttempts
      },
      this.cancellationToken
    )
  }

  /**
   * Disconnect from the WebSocket server
   */
  disconnect(): void {
    this.cancellationToken.cancel()
    this.clearTimers()
    
    if (this.ws) {
      this.ws.close(1000, 'Client disconnect')
      this.ws = null
    }
    
    this.setState('disconnected')
  }

  /**
   * Send a typed message
   */
  send<T extends Record<string, unknown> = Record<string, unknown>>(
    type: MessageType, 
    data: T, 
    options?: { correlationId?: string }
  ): boolean {
    if (this.state !== 'connected' || !this.ws) {
      // Buffer the message if disconnected
      const envelope: WSEnvelope<T> = {
        v: 1,
        t: type,
        seq: ++this.lastSeq,
        corr: options?.correlationId,
        t_wall: new Date().toISOString(),
        data
      }
      
      return this.messageBuffer.enqueue(envelope)
    }

    try {
      const envelope: WSEnvelope<T> = {
        v: 1,
        t: type,
        seq: ++this.lastSeq,
        corr: options?.correlationId,
        t_wall: new Date().toISOString(),
        data
      }

      const message = JSON.stringify(envelope)
      
      if (message.length > (this.config.maxMessageSize ?? 64 * 1024)) {
        throw new Error('Message too large')
      }

      this.ws.send(message)
      return true
    } catch (error) {
      this.events.onError?.(error instanceof Error ? error : new Error(String(error)))
      return false
    }
  }

  /**
   * Get current connection state
   */
  getState(): ConnectionState {
    return this.state
  }

  /**
   * Get connection statistics
   */
  getStats() {
    return {
      state: this.state,
      reconnectAttempt: this.reconnectAttempt,
      bufferedMessages: this.messageBuffer.getStats(),
      lastSeq: this.lastSeq
    }
  }

  private async attemptConnection(): Promise<void> {
    return new Promise<void>((resolve, reject) => {
      try {
        this.ws = new WebSocket(this.config.url)
        
        this.ws.onopen = () => {
          this.setState('connected')
          this.reconnectAttempt = 0
          this.startHeartbeat()
          this.flushBufferedMessages()
          this.events.onConnect?.()
          resolve()
        }

        this.ws.onclose = (event) => {
          this.ws = null
          this.stopHeartbeat()
          
          if (this.cancellationToken.isCancelled) {
            this.setState('disconnected')
            return
          }

          const reason = `WebSocket closed: ${event.code} ${event.reason}`
          this.events.onDisconnect?.(reason)

          if (this.config.reconnect && this.reconnectAttempt < this.config.maxReconnectAttempts) {
            this.scheduleReconnect()
          } else {
            this.setState('failed')
            reject(new Error(reason))
          }
        }

        this.ws.onerror = (event) => {
          const error = new Error(`WebSocket error: ${event}`)
          this.events.onError?.(error)
          reject(error)
        }

        this.ws.onmessage = (event) => {
          try {
            const envelope = JSON.parse(event.data) as WSEnvelope
            this.events.onMessage?.(envelope)
          } catch (error) {
            this.events.onError?.(new Error('Failed to parse WebSocket message'))
          }
        }
      } catch (error) {
        reject(error instanceof Error ? error : new Error(String(error)))
      }
    })
  }

  private scheduleReconnect(): void {
    // Guard against multiple reconnect attempts
    if (this.reconnectTimer) return
    if (this.cancellationToken.isCancelled) return
    if (this.state === 'connected' || this.state === 'connecting') return

    this.setState('reconnecting')
    this.reconnectAttempt++

    const delay = Math.min(
      this.config.reconnectDelay * Math.pow(2, this.reconnectAttempt - 1),
      this.config.maxReconnectDelay
    )

    this.reconnectTimer = window.setTimeout(() => {
      this.reconnectTimer = null
      // Double-check cancellation before attempting connection
      if (!this.cancellationToken.isCancelled && this.state === 'reconnecting') {
        this.attemptConnection().catch(() => {
          // Error handled in onclose
        })
      }
    }, delay)
  }

  private setState(newState: ConnectionState): void {
    if (this.state !== newState) {
      this.state = newState
      this.events.onStateChange?.(newState)
    }
  }

  private startHeartbeat(): void {
    if (!this.config.heartbeatInterval) return

    this.heartbeatTimer = window.setInterval(() => {
      this.send('session.heartbeat', { timestamp: Date.now() })
    }, this.config.heartbeatInterval)
  }

  private stopHeartbeat(): void {
    if (this.heartbeatTimer) {
      clearInterval(this.heartbeatTimer)
      this.heartbeatTimer = null
    }
  }

  private flushBufferedMessages(): void {
    while (!this.messageBuffer.isEmpty()) {
      const message = this.messageBuffer.dequeue()
      if (message && this.ws?.readyState === WebSocket.OPEN) {
        try {
          this.ws.send(JSON.stringify(message))
        } catch (error) {
          console.warn('Failed to send buffered message:', error)
          break
        }
      }
    }
  }

  private clearTimers(): void {
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer)
      this.reconnectTimer = null
    }
    this.stopHeartbeat()
  }
}

/**
 * Create a WebSocket client with default configuration
 */
export function createWSClient(
  url: string, 
  events?: WSClientEvents,
  config: Partial<WSClientConfig> = {}
): WSClient {
  const fullConfig: WSClientConfig = {
    url,
    reconnect: true,
    maxReconnectAttempts: 10,
    reconnectDelay: 1000,
    maxReconnectDelay: 30000,
    heartbeatInterval: 30000,
    maxMessageSize: 64 * 1024,
    maxBufferSize: 1024 * 1024,
    ...config
  }
  return new WSClient(fullConfig, events)
}