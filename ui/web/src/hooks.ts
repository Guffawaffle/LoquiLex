// React hooks for the dual panel UI

import { useEffect, useState, useRef, useCallback, useMemo } from 'react'
import { ConnectionStatus, SessionState, TranscriptLine, WebSocketMessage, ASREvent, MTEvent, UIPreferences } from './types'
import { generateId, throttle, measurePerformance } from './utils'

// Enhanced WebSocket hook with proper protocol handling
export function useWebSocketSession(sessionId: string | null) {
  const [sessionState, setSessionState] = useState<SessionState | null>(null)
  const [connectionStatus, setConnectionStatus] = useState<ConnectionStatus>('offline')
  const wsRef = useRef<WebSocket | null>(null)
  const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null)
  const backoffRef = useRef(500) // Start with 500ms backoff

  const processMessage = useCallback((message: WebSocketMessage) => {
    return measurePerformance(() => {
      if (!sessionId) return

      setSessionState(prevState => {
        if (!prevState) return prevState

        const newState = { ...prevState }
        newState.lastActivity = Date.now()

        switch (message.t) {
          case 'asr.partial': {
            const data = message.data as ASREvent
            const line: TranscriptLine = {
              id: data.segment_id || generateId(),
              text: data.text,
              timestamp: message.t_mono_ns ? Math.floor(message.t_mono_ns / 1_000_000) : Date.now(),
              isFinal: false,
              language: 'source',
              segmentId: data.segment_id,
            }
            newState.currentPartial.source = line
            break
          }

          case 'asr.final': {
            const data = message.data as ASREvent
            const line: TranscriptLine = {
              id: data.segment_id || generateId(),
              text: data.text,
              timestamp: data.start_ms || (message.t_mono_ns ? Math.floor(message.t_mono_ns / 1_000_000) : Date.now()),
              isFinal: true,
              language: 'source',
              segmentId: data.segment_id,
            }
            
            // Add to final lines and clear partial
            newState.sourceLines = [...newState.sourceLines, line].slice(-200) // Keep last 200 lines
            newState.currentPartial.source = undefined
            break
          }

          case 'mt.partial': {
            const data = message.data as MTEvent
            const line: TranscriptLine = {
              id: data.segment_id || generateId(),
              text: data.text,
              timestamp: message.t_mono_ns ? Math.floor(message.t_mono_ns / 1_000_000) : Date.now(),
              isFinal: false,
              language: 'target',
              segmentId: data.segment_id,
            }
            newState.currentPartial.target = line
            break
          }

          case 'mt.final': {
            const data = message.data as MTEvent
            const line: TranscriptLine = {
              id: data.segment_id || generateId(),
              text: data.text,
              timestamp: message.t_mono_ns ? Math.floor(message.t_mono_ns / 1_000_000) : Date.now(),
              isFinal: true,
              language: 'target',
              segmentId: data.segment_id,
            }
            
            // Add to final lines and clear partial
            newState.targetLines = [...newState.targetLines, line].slice(-200) // Keep last 200 lines
            newState.currentPartial.target = undefined
            break
          }

          case 'status': {
            // Handle status updates for performance hints
            const data = message.data
            if (data.stage && data.detail) {
              newState.performanceHint = `${data.stage}: ${data.detail}`
            }
            break
          }

          // Legacy message types for backward compatibility
          case 'partial_en': {
            const line: TranscriptLine = {
              id: generateId(),
              text: message.data.text || '',
              timestamp: Date.now(),
              isFinal: false,
              language: 'source',
            }
            newState.currentPartial.source = line
            break
          }

          case 'final_en': {
            const line: TranscriptLine = {
              id: generateId(),
              text: message.data.text || '',
              timestamp: Date.now(),
              isFinal: true,
              language: 'source',
            }
            newState.sourceLines = [...newState.sourceLines, line].slice(-200)
            newState.currentPartial.source = undefined
            break
          }

          case 'partial_zh': {
            const line: TranscriptLine = {
              id: generateId(),
              text: message.data.text || '',
              timestamp: Date.now(),
              isFinal: false,
              language: 'target',
            }
            newState.currentPartial.target = line
            break
          }

          case 'final_zh': {
            const line: TranscriptLine = {
              id: generateId(),
              text: message.data.text || '',
              timestamp: Date.now(),
              isFinal: true,
              language: 'target',
            }
            newState.targetLines = [...newState.targetLines, line].slice(-200)
            newState.currentPartial.target = undefined
            break
          }
        }

        return newState
      })
    }, 'processMessage')
  }, [sessionId])

  const connectWebSocket = useCallback(() => {
    if (!sessionId || wsRef.current?.readyState === WebSocket.OPEN) {
      return
    }

    try {
      const ws = new WebSocket(`ws://localhost:8000/events/${sessionId}`)
      wsRef.current = ws

      ws.onopen = () => {
        setConnectionStatus('connected')
        backoffRef.current = 500 // Reset backoff on successful connection
        
        if (!sessionState) {
          setSessionState({
            id: sessionId,
            name: `Session ${sessionId.slice(0, 8)}`,
            status: 'connected',
            sourceLines: [],
            targetLines: [],
            currentPartial: {},
            lastActivity: Date.now(),
          })
        } else {
          setSessionState(prev => prev ? { ...prev, status: 'connected' } : prev)
        }
      }

      ws.onmessage = (event) => {
        try {
          // Handle both new protocol and legacy messages
          let message: WebSocketMessage
          
          const data = JSON.parse(event.data)
          if (data.v && data.t) {
            // New protocol message
            message = data as WebSocketMessage
          } else {
            // Legacy message format
            message = {
              v: 1,
              t: data.type || 'unknown',
              data: data,
            }
          }
          
          processMessage(message)
        } catch (error) {
          console.warn('Failed to parse WebSocket message:', error)
        }
      }

      ws.onclose = () => {
        setConnectionStatus('reconnecting')
        setSessionState(prev => prev ? { ...prev, status: 'reconnecting' } : prev)
        
        // Exponential backoff with jitter
        const jitter = Math.random() * 1000
        const delay = Math.min(backoffRef.current + jitter, 8000)
        backoffRef.current = Math.min(backoffRef.current * 2, 8000)
        
        reconnectTimeoutRef.current = setTimeout(connectWebSocket, delay)
      }

      ws.onerror = (error) => {
        console.error('WebSocket error:', error)
        setConnectionStatus('offline')
        setSessionState(prev => prev ? { ...prev, status: 'offline' } : prev)
      }

    } catch (error) {
      console.error('Failed to create WebSocket connection:', error)
      setConnectionStatus('offline')
      setSessionState(prev => prev ? { ...prev, status: 'offline' } : prev)
    }
  }, [sessionId, sessionState, processMessage])

  useEffect(() => {
    if (sessionId) {
      connectWebSocket()
    } else {
      // Clean up when no session
      if (wsRef.current) {
        wsRef.current.close()
        wsRef.current = null
      }
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current)
        reconnectTimeoutRef.current = null
      }
      setSessionState(null)
      setConnectionStatus('offline')
    }

    return () => {
      if (wsRef.current) {
        wsRef.current.close()
        wsRef.current = null
      }
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current)
        reconnectTimeoutRef.current = null
      }
    }
  }, [sessionId, connectWebSocket])

  return {
    sessionState,
    connectionStatus,
    reconnect: connectWebSocket,
  }
}

// Hook for managing UI preferences
export function useUIPreferences() {
  const [preferences, setPreferences] = useState<UIPreferences>(() => {
    try {
      const stored = localStorage.getItem('loquilex-ui-prefs')
      if (stored) {
        const parsed = JSON.parse(stored)
        return {
          theme: parsed.theme || 'dark',
          showTimestamps: parsed.showTimestamps ?? true,
          autoscrollPaused: parsed.autoscrollPaused ?? false,
        }
      }
    } catch (e) {
      // Ignore localStorage errors
    }
    
    return {
      theme: 'dark',
      showTimestamps: true,
      autoscrollPaused: false,
    }
  })

  const updatePreferences = useCallback((updates: Partial<UIPreferences>) => {
    setPreferences(prev => {
      const newPrefs = { ...prev, ...updates }
      try {
        localStorage.setItem('loquilex-ui-prefs', JSON.stringify(newPrefs))
      } catch (e) {
        // Ignore localStorage errors
      }
      return newPrefs
    })
  }, [])

  return {
    preferences,
    updatePreferences,
  }
}

// Hook for auto-scroll management
export function useAutoScroll(isEnabled: boolean) {
  const scrollElementRef = useRef<HTMLElement | null>(null)
  const [isUserScrolling, setIsUserScrolling] = useState(false)
  const scrollTimeoutRef = useRef<NodeJS.Timeout | null>(null)

  const scrollToBottom = useCallback(() => {
    if (scrollElementRef.current && !isUserScrolling && isEnabled) {
      scrollElementRef.current.scrollTop = scrollElementRef.current.scrollHeight
    }
  }, [isUserScrolling, isEnabled])

  const throttledScrollToBottom = useMemo(
    () => throttle(scrollToBottom, 33), // ~30fps
    [scrollToBottom]
  )

  const handleScroll = useCallback(() => {
    if (!scrollElementRef.current) return

    const { scrollTop, scrollHeight, clientHeight } = scrollElementRef.current
    const isAtBottom = scrollTop + clientHeight >= scrollHeight - 10 // 10px tolerance

    if (!isAtBottom) {
      setIsUserScrolling(true)
    } else {
      setIsUserScrolling(false)
    }

    // Clear existing timeout
    if (scrollTimeoutRef.current) {
      clearTimeout(scrollTimeoutRef.current)
    }

    // Set user scrolling to false after 2 seconds of no scroll events
    scrollTimeoutRef.current = setTimeout(() => {
      setIsUserScrolling(false)
    }, 2000)
  }, [])

  const jumpToLive = useCallback(() => {
    setIsUserScrolling(false)
    if (scrollElementRef.current) {
      scrollElementRef.current.scrollTop = scrollElementRef.current.scrollHeight
    }
  }, [])

  useEffect(() => {
    const element = scrollElementRef.current
    if (element) {
      element.addEventListener('scroll', handleScroll, { passive: true })
      return () => {
        element.removeEventListener('scroll', handleScroll)
      }
    }
  }, [handleScroll])

  useEffect(() => {
    return () => {
      if (scrollTimeoutRef.current) {
        clearTimeout(scrollTimeoutRef.current)
      }
    }
  }, [])

  return {
    scrollElementRef,
    isUserScrolling,
    scrollToBottom: throttledScrollToBottom,
    jumpToLive,
  }
}