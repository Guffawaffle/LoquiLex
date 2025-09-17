/**
 * Throttling Utilities - Event cadence capping for WS → UI updates
 * 
 * Ensures no more than 2-10 Hz updates to prevent UI jank while
 * maintaining responsiveness during rapid progress changes.
 */

/**
 * Configuration for throttling behavior
 */
export interface ThrottleConfig {
  /** Maximum frequency in Hz (events per second), clamped to 2-10 Hz */
  maxHz: number
  /** Whether to execute on leading edge */
  leading?: boolean
  /** Whether to execute on trailing edge */
  trailing?: boolean
}

/**
 * Default throttle configuration with 5 Hz cap
 */
export const DEFAULT_THROTTLE_CONFIG: Required<ThrottleConfig> = {
  maxHz: 5,
  leading: true,
  trailing: true
}

/**
 * Throttle function to limit execution frequency
 * Ensures frequency is between 2-10 Hz for UI stability
 */
export function createThrottler<T extends (...args: any[]) => any>(
  fn: T,
  config: Partial<ThrottleConfig> = {}
): T {
  const { maxHz, leading, trailing } = { ...DEFAULT_THROTTLE_CONFIG, ...config }
  
  // Clamp frequency to 2-10 Hz range
  const cappedHz = Math.max(2, Math.min(10, maxHz))
  const interval = 1000 / cappedHz
  
  let lastExecution = 0
  let timeoutId: number | null = null
  let lastArgs: Parameters<T> | null = null
  
  const execute = (args: Parameters<T>) => {
    lastExecution = Date.now()
    return fn.apply(null, args)
  }
  
  const throttled = (...args: Parameters<T>) => {
    const now = Date.now()
    const timeSinceLastExecution = now - lastExecution
    lastArgs = args
    
    // Leading edge execution
    if (leading && timeSinceLastExecution >= interval) {
      return execute(args)
    }
    
    // Schedule trailing edge execution if needed
    if (trailing && !timeoutId) {
      const remainingTime = interval - timeSinceLastExecution
      timeoutId = window.setTimeout(() => {
        timeoutId = null
        if (lastArgs) {
          execute(lastArgs)
          lastArgs = null
        }
      }, Math.max(0, remainingTime))
    }
  }
  
  // Add cancel method to clear pending execution
  ;(throttled as any).cancel = () => {
    if (timeoutId) {
      clearTimeout(timeoutId)
      timeoutId = null
      lastArgs = null
    }
  }
  
  return throttled as T
}

/**
 * Simple rate limiter that tracks recent calls and enforces frequency
 */
export class RateLimiter {
  private calls: number[] = []
  private readonly maxHz: number
  private readonly windowMs: number
  
  constructor(maxHz: number = 5) {
    // Clamp to 2-10 Hz range
    this.maxHz = Math.max(2, Math.min(10, maxHz))
    this.windowMs = 1000 // 1 second window
  }
  
  /**
   * Check if a call is allowed within the rate limit
   */
  isAllowed(): boolean {
    const now = Date.now()
    
    // Remove calls outside the window
    this.calls = this.calls.filter(time => now - time < this.windowMs)
    
    // Check if we're under the limit
    if (this.calls.length < this.maxHz) {
      this.calls.push(now)
      return true
    }
    
    return false
  }
  
  /**
   * Get current call rate in Hz
   */
  getCurrentRate(): number {
    const now = Date.now()
    const recentCalls = this.calls.filter(time => now - time < this.windowMs)
    return recentCalls.length
  }
  
  /**
   * Reset the rate limiter
   */
  reset(): void {
    this.calls = []
  }
}

/**
 * Smooth value changes to prevent rapid UI updates
 */
export class ValueSmoother<T> {
  private lastValue: T | undefined
  private lastUpdate = 0
  private readonly minInterval: number
  private pendingTimeout: number | null = null
  
  constructor(maxHz: number = 5) {
    // Clamp to 2-10 Hz range and convert to interval
    const cappedHz = Math.max(2, Math.min(10, maxHz))
    this.minInterval = 1000 / cappedHz
  }
  
  /**
   * Smooth a value update, returning true if the value should be emitted
   */
  shouldEmit(value: T, forceEmit = false): boolean {
    const now = this.getCurrentTime()
    const timeSinceLastUpdate = now - this.lastUpdate
    
    // Always emit first value or forced updates
    if (forceEmit || this.lastValue === undefined) {
      this.lastValue = value
      this.lastUpdate = now
      return true
    }
    
    // Emit if enough time has passed
    if (timeSinceLastUpdate >= this.minInterval) {
      this.lastValue = value
      this.lastUpdate = now
      return true
    }
    
    // Schedule a delayed emit for the latest value
    if (!this.pendingTimeout) {
      const remainingTime = this.minInterval - timeSinceLastUpdate
      this.pendingTimeout = window.setTimeout(() => {
        this.pendingTimeout = null
        this.lastValue = value
        this.lastUpdate = this.getCurrentTime()
        // Note: Consumer needs to handle this delayed emission
      }, remainingTime)
    }
    
    return false
  }
  
  /**
   * Get current time - can be mocked for testing
   */
  private getCurrentTime(): number {
    return Date.now()
  }
  
  /**
   * Cancel any pending emission
   */
  cancel(): void {
    if (this.pendingTimeout) {
      clearTimeout(this.pendingTimeout)
      this.pendingTimeout = null
    }
  }
  
  /**
   * Get the last emitted value
   */
  getLastValue(): T | undefined {
    return this.lastValue
  }
}