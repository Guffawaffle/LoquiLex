/**
 * Retry and Backoff Utilities
 * 
 * Provides configurable retry logic with exponential backoff,
 * jitter, and cancellation token support.
 */

import type { RetryConfig, CancellationToken } from '../types'

export const DEFAULT_RETRY_CONFIG: RetryConfig = {
  maxAttempts: 3,
  initialDelay: 1000,
  maxDelay: 30000,
  backoffMultiplier: 2,
  jitter: true
}

export class RetryableError extends Error {
  constructor(message: string, public readonly cause?: Error) {
    super(message)
    this.name = 'RetryableError'
  }
}

export class NonRetryableError extends Error {
  constructor(message: string, public readonly cause?: Error) {
    super(message)
    this.name = 'NonRetryableError'
  }
}

/**
 * Calculate the next delay using exponential backoff with optional jitter
 */
export function calculateBackoffDelay(
  attempt: number, 
  config: RetryConfig
): number {
  const { initialDelay, maxDelay, backoffMultiplier, jitter } = config
  
  let delay = initialDelay * Math.pow(backoffMultiplier, attempt)
  delay = Math.min(delay, maxDelay)
  
  if (jitter) {
    // Add ±25% jitter to prevent thundering herd
    const jitterRange = delay * 0.25
    delay += (Math.random() - 0.5) * 2 * jitterRange
  }
  
  return Math.max(0, delay)
}

/**
 * Sleep for the specified duration, respecting cancellation
 */
export function sleep(
  ms: number, 
  cancellationToken?: CancellationToken
): Promise<void> {
  return new Promise((resolve, reject) => {
    if (cancellationToken?.isCancelled) {
      reject(new Error('Operation was cancelled'))
      return
    }

    const timeoutId = setTimeout(resolve, ms)
    
    cancellationToken?.onCancelled(() => {
      clearTimeout(timeoutId)
      reject(new Error('Operation was cancelled'))
    })
  })
}

/**
 * Retry an async operation with exponential backoff
 */
export async function withRetry<T>(
  operation: () => Promise<T>,
  config: Partial<RetryConfig> = {},
  cancellationToken?: CancellationToken
): Promise<T> {
  const finalConfig = { ...DEFAULT_RETRY_CONFIG, ...config }
  let lastError: Error | undefined
  
  for (let attempt = 0; attempt < finalConfig.maxAttempts; attempt++) {
    try {
      cancellationToken?.throwIfCancelled()
      return await operation()
    } catch (error) {
      lastError = error instanceof Error ? error : new Error(String(error))
      
      // Don't retry non-retryable errors
      if (error instanceof NonRetryableError) {
        throw error
      }
      
      // Don't retry on last attempt
      if (attempt === finalConfig.maxAttempts - 1) {
        break
      }
      
      // Calculate backoff delay and wait
      const delay = calculateBackoffDelay(attempt, finalConfig)
      await sleep(delay, cancellationToken)
    }
  }
  
  throw new RetryableError(
    `Operation failed after ${finalConfig.maxAttempts} attempts`,
    lastError
  )
}

/**
 * Create a retry wrapper function with pre-configured settings
 */
export function createRetryWrapper(
  config: Partial<RetryConfig> = {}
) {
  const finalConfig = { ...DEFAULT_RETRY_CONFIG, ...config }
  
  return function retryWrapper<T>(
    operation: () => Promise<T>,
    cancellationToken?: CancellationToken
  ): Promise<T> {
    return withRetry(operation, finalConfig, cancellationToken)
  }
}