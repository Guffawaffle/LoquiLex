import React, { useRef, useState, useCallback, useEffect } from 'react'
import { SessionState, UIPreferences } from '../types'
import { TranscriptPanel, TranscriptPanelRef } from './TranscriptPanel'
import { StatusBar } from './StatusBar'
import { handleKeyboardShortcuts } from '../utils'

interface DualPanelViewProps {
  sessionState: SessionState
  preferences: UIPreferences
  onPreferencesChange: (updates: Partial<UIPreferences>) => void
}

export function DualPanelView({
  sessionState,
  preferences,
  onPreferencesChange,
}: DualPanelViewProps) {
  const sourcePanelRef = useRef<TranscriptPanelRef>(null)
  const targetPanelRef = useRef<TranscriptPanelRef>(null)
  
  const [isSourceUserScrolling, setIsSourceUserScrolling] = useState(false)
  const [isTargetUserScrolling, setIsTargetUserScrolling] = useState(false)
  
  // Determine if we should show "Jump to live" button
  const isAnyUserScrolling = isSourceUserScrolling || isTargetUserScrolling
  const shouldShowJumpToLive = isAnyUserScrolling && !preferences.autoscrollPaused

  // Handle theme cycling
  const handleToggleTheme = useCallback(() => {
    const themeOrder: Array<typeof preferences.theme> = ['dark', 'light', 'system']
    const currentIndex = themeOrder.indexOf(preferences.theme)
    const nextTheme = themeOrder[(currentIndex + 1) % themeOrder.length]
    onPreferencesChange({ theme: nextTheme })
  }, [preferences.theme, onPreferencesChange])

  // Handle timestamp toggle
  const handleToggleTimestamps = useCallback(() => {
    onPreferencesChange({ showTimestamps: !preferences.showTimestamps })
  }, [preferences.showTimestamps, onPreferencesChange])

  // Handle jump to live
  const handleJumpToLive = useCallback(() => {
    sourcePanelRef.current?.jumpToLive()
    targetPanelRef.current?.jumpToLive()
    onPreferencesChange({ autoscrollPaused: false })
  }, [onPreferencesChange])

  // Keyboard shortcuts
  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      handleKeyboardShortcuts(event, {
        onToggleTimestamps: handleToggleTimestamps,
        onToggleTheme: handleToggleTheme,
        onJumpToLive: handleJumpToLive,
      })
    }

    document.addEventListener('keydown', handleKeyDown)
    return () => {
      document.removeEventListener('keydown', handleKeyDown)
    }
  }, [handleToggleTimestamps, handleToggleTheme, handleJumpToLive])

  return (
    <div 
      className="h-screen flex flex-col"
      style={{ backgroundColor: 'var(--color-bg-primary)' }}
    >
      {/* Header with title */}
      <div 
        className="px-4 py-3 border-b"
        style={{ 
          backgroundColor: 'var(--color-bg-primary)',
          borderColor: 'var(--color-border)'
        }}
      >
        <h1 
          className="text-xl font-bold"
          style={{ color: 'var(--color-text-primary)' }}
        >
          LoquiLex — Realtime Bridge
        </h1>
        <p 
          className="text-sm"
          style={{ color: 'var(--color-text-secondary)' }}
        >
          Session: {sessionState.name}
        </p>
      </div>

      {/* Status bar */}
      <StatusBar
        connectionStatus={sessionState.status}
        theme={preferences.theme}
        showTimestamps={preferences.showTimestamps}
        performanceHint={sessionState.performanceHint}
        onToggleTimestamps={handleToggleTimestamps}
        onToggleTheme={handleToggleTheme}
        onJumpToLive={shouldShowJumpToLive ? handleJumpToLive : undefined}
        showJumpToLive={shouldShowJumpToLive}
      />

      {/* Main dual panel content */}
      <div className="flex-1 flex overflow-hidden dual-panel">
        {/* Source panel (left) */}
        <div className="flex-1 min-w-0 panel">
          <TranscriptPanel
            ref={sourcePanelRef}
            title="Source"
            language="EN — ASR"
            lines={sessionState.sourceLines}
            currentPartial={sessionState.currentPartial.source}
            showTimestamps={preferences.showTimestamps}
            isAutoScrollEnabled={!preferences.autoscrollPaused}
            onScrollStateChange={setIsSourceUserScrolling}
            ariaLabel="Source language transcript panel"
          />
        </div>

        {/* Divider */}
        <div 
          className="w-px shrink-0"
          style={{ backgroundColor: 'var(--color-border)' }}
          role="separator"
          aria-orientation="vertical"
        />

        {/* Target panel (right) */}
        <div className="flex-1 min-w-0 panel">
          <TranscriptPanel
            ref={targetPanelRef}
            title="Target"
            language="ZH — MT"
            lines={sessionState.targetLines}
            currentPartial={sessionState.currentPartial.target}
            showTimestamps={preferences.showTimestamps}
            isAutoScrollEnabled={!preferences.autoscrollPaused}
            onScrollStateChange={setIsTargetUserScrolling}
            ariaLabel="Target language transcript panel"
          />
        </div>
      </div>

      {/* Floating jump to live button (alternative position) */}
      {shouldShowJumpToLive && (
        <button
          onClick={handleJumpToLive}
          className="jump-to-live focus-visible:focus"
          aria-label="Jump to live transcript (J)"
          title="Jump to live transcript (Press J)"
        >
          ↓ Jump to live
        </button>
      )}
    </div>
  )
}