/**
 * Unit tests for retry utilities
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import {
  withRetry,
  calculateBackoffDelay,
  sleep,
  createRetryWrapper,
  RetryableError,
  NonRetryableError,
  DEFAULT_RETRY_CONFIG
} from '../utils/retry'
import { createCancellationToken } from '../utils/cancellation'

describe('calculateBackoffDelay', () => {
  it('should calculate exponential backoff correctly', () => {
    const config = { ...DEFAULT_RETRY_CONFIG, jitter: false }
    
    expect(calculateBackoffDelay(0, config)).toBe(1000)
    expect(calculateBackoffDelay(1, config)).toBe(2000)
    expect(calculateBackoffDelay(2, config)).toBe(4000)
  })

  it('should respect max delay', () => {
    const config = { ...DEFAULT_RETRY_CONFIG, maxDelay: 5000, jitter: false }
    
    expect(calculateBackoffDelay(10, config)).toBe(5000)
  })

  it('should add jitter when enabled', () => {
    const config = { ...DEFAULT_RETRY_CONFIG, jitter: true }
    const delay1 = calculateBackoffDelay(1, config)
    const delay2 = calculateBackoffDelay(1, config)
    
    // With jitter, delays should vary
    expect(delay1).toBeGreaterThan(0)
    expect(delay2).toBeGreaterThan(0)
    // They might be the same by chance, but both should be reasonable
    expect(delay1).toBeGreaterThan(1000 * 0.5) // At least 50% of base
    expect(delay1).toBeLessThan(1000 * 3) // At most 3x base
  })
})

describe('sleep', () => {
  beforeEach(() => {
    vi.useFakeTimers()
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('should resolve after specified time', async () => {
    const promise = sleep(1000)
    
    expect(vi.getTimerCount()).toBe(1)
    
    vi.advanceTimersByTime(1000)
    await expect(promise).resolves.toBeUndefined()
  })

  it('should reject when cancelled', async () => {
    const token = createCancellationToken()
    const promise = sleep(1000, token)
    
    token.cancel()
    
    await expect(promise).rejects.toThrow('Operation was cancelled')
  })

  it('should reject immediately if already cancelled', async () => {
    const token = createCancellationToken()
    token.cancel()
    
    const promise = sleep(1000, token)
    
    await expect(promise).rejects.toThrow('Operation was cancelled')
  })
})

describe('withRetry', () => {
  beforeEach(() => {
    vi.useFakeTimers()
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('should succeed on first attempt', async () => {
    const operation = vi.fn().mockResolvedValue('success')
    
    const result = await withRetry(operation, { maxAttempts: 3 })
    
    expect(result).toBe('success')
    expect(operation).toHaveBeenCalledTimes(1)
  })

  it('should retry on failure', async () => {
    const operation = vi.fn()
      .mockRejectedValueOnce(new Error('fail1'))
      .mockRejectedValueOnce(new Error('fail2'))
      .mockResolvedValue('success')
    
    const promise = withRetry(operation, { 
      maxAttempts: 3, 
      initialDelay: 100,
      jitter: false 
    })
    
    // Advance timers to allow retries
    vi.runAllTimersAsync()
    
    const result = await promise
    expect(result).toBe('success')
    expect(operation).toHaveBeenCalledTimes(3)
  })

  it('should fail after max attempts', async () => {
    const operation = vi.fn().mockRejectedValue(new Error('persistent failure'))
    
    const promise = withRetry(operation, { maxAttempts: 2, initialDelay: 100 })
    
    vi.runAllTimersAsync()
    
    await expect(promise).rejects.toThrow('Operation failed after 2 attempts')
    expect(operation).toHaveBeenCalledTimes(2)
  })

  it('should not retry NonRetryableError', async () => {
    const operation = vi.fn().mockRejectedValue(new NonRetryableError('do not retry'))
    
    await expect(withRetry(operation, { maxAttempts: 3 })).rejects.toThrow('do not retry')
    expect(operation).toHaveBeenCalledTimes(1)
  })

  it('should respect cancellation token', async () => {
    const token = createCancellationToken()
    const operation = vi.fn().mockRejectedValue(new Error('fail'))
    
    const promise = withRetry(operation, { maxAttempts: 3 }, token)
    
    token.cancel()
    
    await expect(promise).rejects.toThrow('Operation was cancelled')
  })
})

describe('createRetryWrapper', () => {
  it('should create a wrapper with pre-configured settings', async () => {
    const retryWrapper = createRetryWrapper({ maxAttempts: 2 })
    const operation = vi.fn().mockResolvedValue('success')
    
    const result = await retryWrapper(operation)
    
    expect(result).toBe('success')
    expect(operation).toHaveBeenCalledTimes(1)
  })
})

describe('RetryableError', () => {
  it('should create error with cause', () => {
    const cause = new Error('root cause')
    const error = new RetryableError('wrapper', cause)
    
    expect(error.name).toBe('RetryableError')
    expect(error.message).toBe('wrapper')
    expect(error.cause).toBe(cause)
  })
})

describe('NonRetryableError', () => {
  it('should create error with cause', () => {
    const cause = new Error('root cause')
    const error = new NonRetryableError('wrapper', cause)
    
    expect(error.name).toBe('NonRetryableError')
    expect(error.message).toBe('wrapper')
    expect(error.cause).toBe(cause)
  })
})