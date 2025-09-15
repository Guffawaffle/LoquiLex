// Utility functions for the dual panel UI

import { Theme, UIPreferences } from './types'

// Theme management
export function getStoredTheme(): Theme {
  try {
    const stored = localStorage.getItem('loquilex-theme')
    if (stored && ['light', 'dark', 'system'].includes(stored)) {
      return stored as Theme
    }
  } catch (e) {
    // localStorage might not be available
  }
  return 'dark' // Default to dark theme as per requirements
}

export function setStoredTheme(theme: Theme): void {
  try {
    localStorage.setItem('loquilex-theme', theme)
  } catch (e) {
    // localStorage might not be available
  }
}

export function getEffectiveTheme(theme: Theme): 'light' | 'dark' {
  if (theme === 'system') {
    return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'
  }
  return theme
}

export function applyTheme(theme: Theme): void {
  const effectiveTheme = getEffectiveTheme(theme)
  document.documentElement.setAttribute('data-theme', effectiveTheme)
}

// UI Preferences management
export function getStoredPreferences(): UIPreferences {
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
    // localStorage might not be available or JSON is invalid
  }
  
  return {
    theme: 'dark',
    showTimestamps: true,
    autoscrollPaused: false,
  }
}

export function setStoredPreferences(prefs: UIPreferences): void {
  try {
    localStorage.setItem('loquilex-ui-prefs', JSON.stringify(prefs))
  } catch (e) {
    // localStorage might not be available
  }
}

// Timestamp formatting
export function formatTimestamp(timestampMs: number): string {
  const totalSeconds = Math.floor(timestampMs / 1000)
  const milliseconds = timestampMs % 1000
  const minutes = Math.floor(totalSeconds / 60)
  const seconds = totalSeconds % 60
  const hours = Math.floor(minutes / 60)
  const displayMinutes = minutes % 60

  if (hours > 0) {
    return `${hours.toString().padStart(2, '0')}:${displayMinutes.toString().padStart(2, '0')}:${seconds.toString().padStart(2, '0')}.${milliseconds.toString().padStart(3, '0')}`
  } else {
    return `${displayMinutes.toString().padStart(2, '0')}:${seconds.toString().padStart(2, '0')}.${milliseconds.toString().padStart(3, '0')}`
  }
}

// Keyboard shortcut handling
export function handleKeyboardShortcuts(
  event: KeyboardEvent,
  handlers: {
    onToggleTimestamps?: () => void
    onToggleTheme?: () => void
    onJumpToLive?: () => void
  }
): boolean {
  // Only handle shortcuts when not in an input field
  if (event.target instanceof HTMLInputElement || 
      event.target instanceof HTMLTextAreaElement || 
      event.target instanceof HTMLSelectElement) {
    return false
  }

  const key = event.key.toLowerCase()
  
  if (key === 't' && !event.ctrlKey && !event.metaKey && !event.altKey) {
    event.preventDefault()
    handlers.onToggleTimestamps?.()
    return true
  }
  
  if (key === 'd' && !event.ctrlKey && !event.metaKey && !event.altKey) {
    event.preventDefault()
    handlers.onToggleTheme?.()
    return true
  }
  
  if (key === 'j' && !event.ctrlKey && !event.metaKey && !event.altKey) {
    event.preventDefault()
    handlers.onJumpToLive?.()
    return true
  }
  
  return false
}

// Performance helpers
export function debounce<T extends (...args: any[]) => any>(
  func: T,
  wait: number
): (...args: Parameters<T>) => void {
  let timeout: NodeJS.Timeout | null = null
  
  return (...args: Parameters<T>) => {
    if (timeout) {
      clearTimeout(timeout)
    }
    timeout = setTimeout(() => {
      func(...args)
    }, wait)
  }
}

export function throttle<T extends (...args: any[]) => any>(
  func: T,
  limit: number
): (...args: Parameters<T>) => void {
  let inThrottle = false
  
  return (...args: Parameters<T>) => {
    if (!inThrottle) {
      func(...args)
      inThrottle = true
      setTimeout(() => {
        inThrottle = false
      }, limit)
    }
  }
}

// Copy to clipboard
export async function copyToClipboard(text: string): Promise<boolean> {
  try {
    await navigator.clipboard.writeText(text)
    return true
  } catch (err) {
    // Fallback for older browsers
    try {
      const textArea = document.createElement('textarea')
      textArea.value = text
      textArea.style.position = 'fixed'
      textArea.style.opacity = '0'
      document.body.appendChild(textArea)
      textArea.focus()
      textArea.select()
      const successful = document.execCommand('copy')
      document.body.removeChild(textArea)
      return successful
    } catch (fallbackErr) {
      return false
    }
  }
}

// Generate unique IDs
export function generateId(): string {
  return Math.random().toString(36).substring(2) + Date.now().toString(36)
}

// Performance monitoring
export function measurePerformance<T>(
  operation: () => T,
  label: string = 'operation'
): T {
  const start = performance.now()
  const result = operation()
  const end = performance.now()
  const duration = end - start
  
  if (duration > 16) { // Log if operation takes more than one frame (16ms)
    console.warn(`Performance: ${label} took ${duration.toFixed(2)}ms`)
  }
  
  return result
}