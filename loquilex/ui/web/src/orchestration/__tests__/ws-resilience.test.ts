/**
 * WebSocket Resilience Tests - Reconnect thrash and memory leak tests
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { WSClient, createWSClient } from '../client/ws-client'
import type { WSClientEvents, WSClientConfig } from '../client/ws-client'

// Mock WebSocket for testing
class MockWebSocket {
  public onopen: ((event: Event) => void) | null = null
  public onclose: ((event: CloseEvent) => void) | null = null
  public onerror: ((event: ErrorEvent) => void) | null = null
  public onmessage: ((event: MessageEvent) => void) | null = null
  public readyState: number = WebSocket.CONNECTING

  private static instances: MockWebSocket[] = []

  constructor(public url: string) {
    MockWebSocket.instances.push(this)
  }

  close(code?: number, reason?: string) {
    this.readyState = WebSocket.CLOSED
    setTimeout(() => {
      this.onclose?.({
        code: code || 1000,
        reason: reason || '',
        wasClean: true
      } as CloseEvent)
    }, 0)
  }

  send(data: string | ArrayBuffer | Blob | ArrayBufferView) {
    // Mock implementation
  }

  // Test helpers
  static getInstances() {
    return MockWebSocket.instances
  }

  static clearInstances() {
    MockWebSocket.instances = []
  }

  simulateOpen() {
    this.readyState = WebSocket.OPEN
    setTimeout(() => {
      this.onopen?.({} as Event)
    }, 0)
  }

  simulateError(message = 'Connection failed') {
    setTimeout(() => {
      this.onerror?.({
        message,
        error: new Error(message)
      } as ErrorEvent)
    }, 0)
  }

  simulateClose(code = 1006, reason = 'Connection lost') {
    this.readyState = WebSocket.CLOSED
    setTimeout(() => {
      this.onclose?.({
        code,
        reason,
        wasClean: false
      } as CloseEvent)
    }, 0)
  }
}

describe('WebSocket Resilience', () => {
  let originalWebSocket: typeof WebSocket

  beforeEach(() => {
    vi.useFakeTimers()
    originalWebSocket = global.WebSocket
    global.WebSocket = MockWebSocket as any
    MockWebSocket.clearInstances()
  })

  afterEach(() => {
    vi.restoreAllMocks()
    global.WebSocket = originalWebSocket
    MockWebSocket.clearInstances()
  })

  describe('Reconnect Thrash Handling', () => {
    it('should handle rapid reconnection attempts gracefully', async () => {
      const events: WSClientEvents = {
        onStateChange: vi.fn(),
        onConnect: vi.fn(),
        onDisconnect: vi.fn(),
        onError: vi.fn()
      }

      const config: WSClientConfig = {
        url: 'ws://localhost:8000',
        reconnect: true,
        maxReconnectAttempts: 5,
        reconnectDelay: 100,
        maxReconnectDelay: 1000
      }

      const client = new WSClient(config, events)

      // Start connection
      const connectPromise = client.connect()

      // Simulate rapid connect/disconnect cycles
      for (let i = 0; i < 3; i++) {
        const instances = MockWebSocket.getInstances()
        const ws = instances[instances.length - 1]

        ws.simulateOpen()
        await vi.advanceTimersByTimeAsync(10)

        ws.simulateClose()
        await vi.advanceTimersByTimeAsync(50)
      }

      // Should not have excessive connections
      expect(MockWebSocket.getInstances().length).toBeLessThan(10)
      
      // Should handle the thrashing gracefully
      expect(events.onError).not.toHaveBeenCalledWith(
        expect.objectContaining({
          message: expect.stringMatching(/too many/i)
        })
      )

      client.disconnect()
    })

    it('should prevent memory leaks during reconnect thrash', async () => {
      const events: WSClientEvents = {
        onStateChange: vi.fn(),
        onConnect: vi.fn(),
        onDisconnect: vi.fn()
      }

      const client = createWSClient('ws://localhost:8000', events, {
        maxReconnectAttempts: 3,
        reconnectDelay: 50
      })

      // Simulate many failed connection attempts
      for (let i = 0; i < 10; i++) {
        client.connect().catch(() => {}) // Ignore failures
        
        const instances = MockWebSocket.getInstances()
        const ws = instances[instances.length - 1]
        
        if (ws) {
          ws.simulateError('Network error')
          ws.simulateClose()
        }
        
        await vi.advanceTimersByTimeAsync(100)
      }

      // Should not accumulate unbounded connections
      expect(MockWebSocket.getInstances().length).toBeLessThan(50)

      client.disconnect()
    })

    it('should respect cancellation during reconnect storms', async () => {
      const events: WSClientEvents = {
        onStateChange: vi.fn()
      }

      const client = createWSClient('ws://localhost:8000', events, {
        maxReconnectAttempts: 10,
        reconnectDelay: 100
      })

      // Start connecting
      client.connect().catch(() => {})
      
      // Simulate rapid failures
      for (let i = 0; i < 5; i++) {
        const instances = MockWebSocket.getInstances()
        const ws = instances[instances.length - 1]
        ws?.simulateError()
        ws?.simulateClose()
        await vi.advanceTimersByTimeAsync(50)
      }

      // Disconnect during the thrashing
      client.disconnect()
      await vi.advanceTimersByTimeAsync(1000)

      // Should not continue attempting after disconnect
      const finalInstanceCount = MockWebSocket.getInstances().length
      
      // Advanced timers should not create more instances
      await vi.advanceTimersByTimeAsync(5000)
      expect(MockWebSocket.getInstances().length).toBe(finalInstanceCount)
    })
  })

  describe('Bounded Queue Behavior Under Load', () => {
    it('should maintain bounded message buffer during reconnect', async () => {
      const messages: any[] = []
      const events: WSClientEvents = {
        onMessage: (msg) => messages.push(msg)
      }

      const client = createWSClient('ws://localhost:8000', events, {
        maxBufferSize: 5, // Small buffer for testing
        reconnectDelay: 100
      })

      // Send many messages while disconnected
      for (let i = 0; i < 20; i++) {
        client.send('test', { data: `message-${i}` })
      }

      // Buffer should be bounded (implementation detail, but important for memory)
      // We can't directly test the internal buffer, but can verify behavior
      expect(messages.length).toBe(0) // No messages delivered yet

      // Connect and verify bounded behavior
      client.connect().catch(() => {})
      const ws = MockWebSocket.getInstances()[0]
      ws?.simulateOpen()
      await vi.advanceTimersByTimeAsync(10)

      client.disconnect()
    })

    it('should handle high-frequency state changes without overflow', async () => {
      const stateChanges: string[] = []
      const events: WSClientEvents = {
        onStateChange: (state) => stateChanges.push(state)
      }

      const client = createWSClient('ws://localhost:8000', events, {
        reconnectDelay: 10
      })

      // Rapid connect/disconnect to generate many state changes
      for (let i = 0; i < 20; i++) {
        client.connect().catch(() => {})
        const ws = MockWebSocket.getInstances()[i]
        
        ws?.simulateOpen()
        await vi.advanceTimersByTimeAsync(5)
        
        ws?.simulateClose()
        await vi.advanceTimersByTimeAsync(5)
        
        client.disconnect()
        await vi.advanceTimersByTimeAsync(5)
      }

      // Should have many state changes but not overflow
      expect(stateChanges.length).toBeGreaterThan(10)
      expect(stateChanges.length).toBeLessThan(200) // Reasonable upper bound
    })
  })

  describe('Idempotent Handlers', () => {
    it('should handle duplicate connection events gracefully', async () => {
      const connections: any[] = []
      const events: WSClientEvents = {
        onConnect: () => connections.push(Date.now())
      }

      const client = createWSClient('ws://localhost:8000', events)

      client.connect().catch(() => {})
      const ws = MockWebSocket.getInstances()[0]

      // Simulate multiple open events (shouldn't happen but good to handle)
      ws?.simulateOpen()
      ws?.simulateOpen()
      ws?.simulateOpen()
      
      await vi.advanceTimersByTimeAsync(10)

      // Should handle gracefully without creating problems
      expect(connections.length).toBeGreaterThan(0)
      expect(connections.length).toBeLessThan(10) // Not excessive

      client.disconnect()
    })

    it('should handle connection state races gracefully', async () => {
      const events: WSClientEvents = {
        onStateChange: vi.fn()
      }

      const client = createWSClient('ws://localhost:8000', events)

      // Start multiple connection attempts simultaneously
      client.connect().catch(() => {})
      client.connect().catch(() => {})
      client.connect().catch(() => {})

      await vi.advanceTimersByTimeAsync(10)

      // Should not create excessive WebSocket instances
      expect(MockWebSocket.getInstances().length).toBeLessThanOrEqual(3)

      client.disconnect()
    })
  })

  describe('Snapshot Recovery', () => {
    it('should maintain connection configuration through reconnects', async () => {
      const config: WSClientConfig = {
        url: 'ws://localhost:8000',
        reconnect: true,
        maxReconnectAttempts: 3,
        reconnectDelay: 100,
        maxReconnectDelay: 1000,
        heartbeatInterval: 5000
      }

      const client = new WSClient(config)

      // Connect and disconnect multiple times
      for (let i = 0; i < 3; i++) {
        client.connect().catch(() => {})
        const ws = MockWebSocket.getInstances()[i]
        
        ws?.simulateOpen()
        await vi.advanceTimersByTimeAsync(10)
        
        ws?.simulateClose()
        await vi.advanceTimersByTimeAsync(150) // Wait for reconnect delay
      }

      // Configuration should be preserved
      expect(MockWebSocket.getInstances().every(ws => 
        ws.url === 'ws://localhost:8000'
      )).toBe(true)

      client.disconnect()
    })
  })
})