/**
 * Structured logger for UI orchestrator with offline safety and data redaction
 */

import { DataRedactor } from './data-redactor'

export enum LogLevel {
  DEBUG = 'debug',
  INFO = 'info',
  WARNING = 'warning',
  ERROR = 'error',
  CRITICAL = 'critical'
}

export interface LogEntry {
  timestamp: number
  iso_timestamp: string
  level: LogLevel
  component: string
  session_id: string
  session_time: number
  message: string
  [key: string]: any
}

export interface LoggerConfig {
  component: string
  session_id?: string
  console_enabled?: boolean
  local_storage_key?: string
  redactor?: DataRedactor
}

/**
 * Offline-safe structured logger for browser environment
 */
export class StructuredLogger {
  private component: string
  private session_id: string
  private start_time: number
  private console_enabled: boolean
  private local_storage_key?: string
  private redactor: DataRedactor

  constructor(config: LoggerConfig) {
    this.component = config.component
    this.session_id = config.session_id || this.generateSessionId()
    this.start_time = Date.now()
    this.console_enabled = config.console_enabled ?? true
    this.local_storage_key = config.local_storage_key
    this.redactor = config.redactor || new DataRedactor()
  }

  private generateSessionId(): string {
    // Use secure random values if available
    if (typeof window !== 'undefined' && window.crypto && window.crypto.getRandomValues) {
      const array = new Uint32Array(2); // 2*32 bits = 64 bits (enough for 8 base36 characters)
      window.crypto.getRandomValues(array);
      // Convert each part to base36 and join them
      return Array.from(array).map(num => num.toString(36)).join('').substring(0, 8);
    } else {
      // Fallback to a less secure method if crypto isn't available (should be rare)
      return (Date.now().toString(36) + Math.random().toString(36).substring(2, 10)).substring(0, 8);
    }
  }

  private formatLogEntry(level: LogLevel, message: string, context: Record<string, any>): LogEntry {
    // Apply redaction to context
    const safe_context = this.redactor.redactObject(context)
    
    return {
      timestamp: Date.now(),
      iso_timestamp: new Date().toISOString(),
      level,
      component: this.component,
      session_id: this.session_id,
      session_time: Date.now() - this.start_time,
      message,
      ...safe_context
    }
  }

  private writeLog(entry: LogEntry): void {
    const json_line = JSON.stringify(entry)

    // Console output (if enabled)
    if (this.console_enabled) {
      const console_method = this.getConsoleMethod(entry.level)
      console_method(`[${entry.component}] ${entry.message}`, entry)
    }

    // Local storage (if configured and available)
    if (this.local_storage_key && typeof Storage !== 'undefined') {
      try {
        const existing = localStorage.getItem(this.local_storage_key) || ''
        const updated = existing + json_line + '\n'
        
        // Keep only last 1000 lines to prevent storage overflow
        const lines = updated.split('\n')
        if (lines.length > 1000) {
          localStorage.setItem(this.local_storage_key, lines.slice(-1000).join('\n'))
        } else {
          localStorage.setItem(this.local_storage_key, updated)
        }
      } catch (e) {
        // Storage may be full or unavailable, fail silently for offline safety
      }
    }
  }

  private getConsoleMethod(level: LogLevel): (...args: any[]) => void {
    switch (level) {
      case LogLevel.DEBUG:
        return console.debug
      case LogLevel.INFO:
        return console.info
      case LogLevel.WARNING:
        return console.warn
      case LogLevel.ERROR:
      case LogLevel.CRITICAL:
        return console.error
      default:
        return console.log
    }
  }

  debug(message: string, context: Record<string, any> = {}): void {
    const entry = this.formatLogEntry(LogLevel.DEBUG, message, context)
    this.writeLog(entry)
  }

  info(message: string, context: Record<string, any> = {}): void {
    const entry = this.formatLogEntry(LogLevel.INFO, message, context)
    this.writeLog(entry)
  }

  warning(message: string, context: Record<string, any> = {}): void {
    const entry = this.formatLogEntry(LogLevel.WARNING, message, context)
    this.writeLog(entry)
  }

  error(message: string, context: Record<string, any> = {}): void {
    const entry = this.formatLogEntry(LogLevel.ERROR, message, context)
    this.writeLog(entry)
  }

  critical(message: string, context: Record<string, any> = {}): void {
    const entry = this.formatLogEntry(LogLevel.CRITICAL, message, context)
    this.writeLog(entry)
  }

  /**
   * Get all logs from local storage
   */
  getLogs(): LogEntry[] {
    if (!this.local_storage_key || typeof Storage === 'undefined') {
      return []
    }

    try {
      const stored = localStorage.getItem(this.local_storage_key) || ''
      return stored
        .split('\n')
        .filter(line => line.trim())
        .map(line => JSON.parse(line))
    } catch (e) {
      return []
    }
  }

  /**
   * Clear stored logs
   */
  clearLogs(): void {
    if (this.local_storage_key && typeof Storage !== 'undefined') {
      localStorage.removeItem(this.local_storage_key)
    }
  }
}

/**
 * Factory function to create structured logger
 */
export function createLogger(config: LoggerConfig): StructuredLogger {
  return new StructuredLogger(config)
}