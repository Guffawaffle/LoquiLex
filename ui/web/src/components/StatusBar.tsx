import React from 'react'
import { ConnectionStatus, Theme } from '../types'

interface StatusBarProps {
  connectionStatus: ConnectionStatus
  theme: Theme
  showTimestamps: boolean
  performanceHint?: string
  onToggleTimestamps: () => void
  onToggleTheme: () => void
  onJumpToLive?: () => void
  showJumpToLive?: boolean
}

export function StatusBar({
  connectionStatus,
  theme,
  showTimestamps,
  performanceHint,
  onToggleTimestamps,
  onToggleTheme,
  onJumpToLive,
  showJumpToLive = false,
}: StatusBarProps) {
  const getConnectionStatusDisplay = () => {
    switch (connectionStatus) {
      case 'connected':
        return { text: 'Connected', className: 'status-connected' }
      case 'reconnecting':
        return { text: 'Reconnecting', className: 'status-reconnecting' }
      case 'offline':
        return { text: 'Offline', className: 'status-offline' }
    }
  }

  const getThemeDisplay = () => {
    switch (theme) {
      case 'light':
        return 'Light'
      case 'dark':
        return 'Dark'
      case 'system':
        return 'System'
    }
  }

  const statusDisplay = getConnectionStatusDisplay()

  return (
    <div 
      className="flex items-center justify-between px-4 py-2 border-b text-sm"
      style={{ 
        backgroundColor: 'var(--color-bg-primary)',
        borderColor: 'var(--color-border)',
        color: 'var(--color-text-secondary)'
      }}
      role="banner"
      aria-label="Status bar"
    >
      {/* Left side - Connection status and performance */}
      <div className="flex items-center gap-4">
        <div className="flex items-center gap-2">
          <div 
            className={`w-2 h-2 rounded-full ${
              connectionStatus === 'connected' ? 'bg-green-500' :
              connectionStatus === 'reconnecting' ? 'bg-yellow-500' :
              'bg-red-500'
            }`}
            aria-label={`Connection status: ${statusDisplay.text}`}
          />
          <span className={statusDisplay.className}>
            {statusDisplay.text}
          </span>
        </div>
        
        {performanceHint && (
          <div 
            className="text-xs px-2 py-1 rounded"
            style={{ 
              backgroundColor: 'var(--color-bg-tertiary)',
              color: 'var(--color-text-muted)'
            }}
            title="Performance metric"
          >
            {performanceHint}
          </div>
        )}
      </div>

      {/* Center - Controls */}
      <div className="flex items-center gap-4">
        {/* Timestamps toggle */}
        <label className="flex items-center gap-2 cursor-pointer">
          <span>Timestamps</span>
          <button
            onClick={onToggleTimestamps}
            className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors focus-visible:focus ${
              showTimestamps ? 'bg-blue-600' : 'bg-gray-300 dark:bg-gray-600'
            }`}
            role="switch"
            aria-checked={showTimestamps}
            aria-label="Toggle timestamps (T)"
            title="Toggle timestamps (Press T)"
          >
            <span
              className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
                showTimestamps ? 'translate-x-6' : 'translate-x-1'
              }`}
            />
          </button>
        </label>

        {/* Theme toggle */}
        <label className="flex items-center gap-2">
          <span>Theme:</span>
          <button
            onClick={onToggleTheme}
            className="px-3 py-1 rounded-md transition-colors focus-visible:focus"
            style={{ 
              backgroundColor: 'var(--color-bg-tertiary)',
              color: 'var(--color-text-primary)'
            }}
            aria-label="Toggle theme (D)"
            title="Toggle theme (Press D)"
          >
            {getThemeDisplay()}
          </button>
        </label>
      </div>

      {/* Right side - Jump to live button */}
      <div className="flex items-center gap-2">
        {showJumpToLive && onJumpToLive && (
          <button
            onClick={onJumpToLive}
            className="px-3 py-1 text-sm rounded-md transition-all focus-visible:focus"
            style={{ 
              backgroundColor: 'var(--color-accent)',
              color: 'white'
            }}
            title="Jump to live transcript (Press J)"
            aria-label="Jump to live transcript"
          >
            Jump to live
          </button>
        )}
        
        <div className="text-xs" style={{ color: 'var(--color-text-muted)' }}>
          <kbd className="px-1 py-0.5 rounded text-xs" style={{ backgroundColor: 'var(--color-bg-tertiary)' }}>
            T
          </kbd>{' '}
          Timestamps •{' '}
          <kbd className="px-1 py-0.5 rounded text-xs" style={{ backgroundColor: 'var(--color-bg-tertiary)' }}>
            D
          </kbd>{' '}
          Theme
          {showJumpToLive && (
            <>
              {' • '}
              <kbd className="px-1 py-0.5 rounded text-xs" style={{ backgroundColor: 'var(--color-bg-tertiary)' }}>
                J
              </kbd>{' '}
              Jump
            </>
          )}
        </div>
      </div>
    </div>
  )
}