import React, { useEffect, useImperativeHandle, forwardRef } from 'react'
import { TranscriptLine } from '../types'
import { formatTimestamp, copyToClipboard } from '../utils'
import { useAutoScroll } from '../hooks'

interface TranscriptPanelProps {
  title: string
  language: string
  lines: TranscriptLine[]
  currentPartial?: TranscriptLine
  showTimestamps: boolean
  isAutoScrollEnabled: boolean
  onScrollStateChange?: (isUserScrolling: boolean) => void
  ariaLabel?: string
}

export interface TranscriptPanelRef {
  scrollToBottom: () => void
  jumpToLive: () => void
}

export const TranscriptPanel = forwardRef<TranscriptPanelRef, TranscriptPanelProps>(
  ({
    title,
    language,
    lines,
    currentPartial,
    showTimestamps,
    isAutoScrollEnabled,
    onScrollStateChange,
    ariaLabel
  }, ref) => {
    const {
      scrollElementRef,
      isUserScrolling,
      scrollToBottom,
      jumpToLive,
    } = useAutoScroll(isAutoScrollEnabled)

    // Expose methods to parent component
    useImperativeHandle(ref, () => ({
      scrollToBottom,
      jumpToLive,
    }), [scrollToBottom, jumpToLive])

    // Notify parent of scroll state changes
    useEffect(() => {
      onScrollStateChange?.(isUserScrolling)
    }, [isUserScrolling, onScrollStateChange])

    // Auto-scroll when new content arrives
    useEffect(() => {
      if (lines.length > 0 || currentPartial) {
        scrollToBottom()
      }
    }, [lines.length, currentPartial?.text, scrollToBottom])

    const handleCopyLine = async (line: TranscriptLine) => {
      const textToCopy = showTimestamps
        ? `[${formatTimestamp(line.t_start_ms)}] ${line.text}`
        : line.text

      if (await copyToClipboard(textToCopy)) {
        // Could add a toast notification here
        console.log('Copied to clipboard:', textToCopy)
      }
    }

    const handleCopyAll = async () => {
      const allLines = [...lines]
      if (currentPartial) {
        allLines.push(currentPartial)
      }

      const textToCopy = allLines
        .map(line => showTimestamps
          ? `[${formatTimestamp(line.t_start_ms)}] ${line.text}`
          : line.text
        )
        .join('\n')

      if (await copyToClipboard(textToCopy)) {
        console.log('Copied all lines to clipboard')
      }
    }

    return (
      <div className="flex flex-col h-full" role="region" aria-label={ariaLabel || `${title} transcript`}>
        {/* Header */}
        <div className="flex items-center justify-between p-3 border-b"
             style={{ borderColor: 'var(--color-border)' }}>
          <div>
            <h2 className="text-lg font-semibold" style={{ color: 'var(--color-text-primary)' }}>
              {title}
            </h2>
            <p className="text-sm" style={{ color: 'var(--color-text-secondary)' }}>
              {language}
            </p>
          </div>
          <button
            onClick={handleCopyAll}
            className="px-3 py-1 text-sm rounded-md transition-colors focus-visible:focus"
            style={{
              backgroundColor: 'var(--color-bg-tertiary)',
              color: 'var(--color-text-secondary)'
            }}
            title="Copy all transcript text"
          >
            Copy All
          </button>
        </div>

        {/* Transcript content */}
        <div
          ref={scrollElementRef as React.RefObject<HTMLDivElement>}
          className="flex-1 overflow-y-auto p-3 space-y-2 panel-scroll"
          style={{ backgroundColor: 'var(--color-bg-secondary)' }}
          role="log"
          aria-live="polite"
          aria-label={`${title} transcript content`}
        >
          {lines.length === 0 && !currentPartial && (
            <div
              className="text-center py-8"
              style={{ color: 'var(--color-text-muted)' }}
            >
              Waiting for transcript...
            </div>
          )}

          {/* Final transcript lines */}
          {lines.map((line) => (
            <div
              key={line.utterance_id + ':' + line.segment_seq}
              className="transcript-line final group cursor-pointer"
              onClick={() => handleCopyLine(line)}
              tabIndex={0}
              role="button"
              aria-label={`Copy transcript line: ${line.text}`}
              onKeyDown={(e) => {
                if (e.key === 'Enter' || e.key === ' ') {
                  e.preventDefault()
                  handleCopyLine(line)
                }
              }}
            >
              <div className="flex items-start gap-2">
                {showTimestamps && (
                  <span
                    className="text-xs font-mono shrink-0 mt-0.5"
                    style={{ color: 'var(--color-text-muted)' }}
                    aria-label={`Timestamp ${formatTimestamp(line.t_start_ms)}`}
                  >
                    [{formatTimestamp(line.t_start_ms)}]
                  </span>
                )}
                <span
                  className="flex-1"
                  style={{ color: 'var(--color-final)' }}
                >
                  {line.text}
                </span>
                <span
                  className="opacity-0 group-hover:opacity-100 text-xs transition-opacity"
                  style={{ color: 'var(--color-text-muted)' }}
                >
                  Click to copy
                </span>
              </div>
            </div>
          ))}

          {/* Current partial line */}
          {currentPartial && (
            <div
              className="transcript-line partial"
              aria-label={`Partial transcript: ${currentPartial.text}`}
            >
              <div className="flex items-start gap-2">
                {showTimestamps && (
                  <span
                    className="text-xs font-mono shrink-0 mt-0.5"
                    style={{ color: 'var(--color-text-muted)' }}
                  >
                    [{formatTimestamp(currentPartial.t_start_ms)}]
                  </span>
                )}
                <span
                  className="flex-1"
                  style={{ color: 'var(--color-partial)' }}
                >
                  {currentPartial.text}
                  <span className="animate-pulse ml-1">|</span>
                </span>
                <span
                  className="text-xs"
                  style={{ color: 'var(--color-text-muted)' }}
                >
                  (partial)
                </span>
              </div>
            </div>
          )}
        </div>

        {/* Status footer */}
        <div
          className="p-2 text-xs border-t"
          style={{
            borderColor: 'var(--color-border)',
            backgroundColor: 'var(--color-bg-primary)',
            color: 'var(--color-text-muted)'
          }}
        >
          {lines.length} final lines
          {currentPartial && ' • Live'}
          {isUserScrolling && ' • Scrolled up'}
        </div>
      </div>
    )
  }
)

TranscriptPanel.displayName = 'TranscriptPanel'