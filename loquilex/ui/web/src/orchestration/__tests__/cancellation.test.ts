/**
 * Unit tests for cancellation utilities
 */

import { describe, it, expect, vi } from 'vitest'
import {
  CancellationTokenImpl,
  CancellationError,
  createCancellationToken,
  createTimeoutToken,
  combineCancellationTokens,
  raceWithCancellation
} from '../utils/cancellation'

describe('CancellationTokenImpl', () => {
  it('should start uncancelled', () => {
    const token = new CancellationTokenImpl()
    
    expect(token.isCancelled).toBe(false)
  })

  it('should be cancelled after cancel() is called', () => {
    const token = new CancellationTokenImpl()
    
    token.cancel()
    
    expect(token.isCancelled).toBe(true)
  })

  it('should execute callbacks on cancellation', () => {
    const token = new CancellationTokenImpl()
    const callback = vi.fn()
    
    token.onCancelled(callback)
    token.cancel()
    
    expect(callback).toHaveBeenCalledTimes(1)
  })

  it('should execute callback immediately if already cancelled', () => {
    const token = new CancellationTokenImpl()
    const callback = vi.fn()
    
    token.cancel()
    token.onCancelled(callback)
    
    expect(callback).toHaveBeenCalledTimes(1)
  })

  it('should handle callback errors gracefully', () => {
    const token = new CancellationTokenImpl()
    const errorCallback = vi.fn().mockImplementation(() => {
      throw new Error('callback error')
    })
    const goodCallback = vi.fn()
    
    // Mock console.warn to avoid noise in test output
    const consoleSpy = vi.spyOn(console, 'warn').mockImplementation(() => {})
    
    token.onCancelled(errorCallback)
    token.onCancelled(goodCallback)
    token.cancel()
    
    expect(errorCallback).toHaveBeenCalledTimes(1)
    expect(goodCallback).toHaveBeenCalledTimes(1)
    expect(consoleSpy).toHaveBeenCalled()
    
    consoleSpy.mockRestore()
  })

  it('should throw when throwIfCancelled is called on cancelled token', () => {
    const token = new CancellationTokenImpl()
    
    token.cancel()
    
    expect(() => token.throwIfCancelled()).toThrow(CancellationError)
  })

  it('should not throw when throwIfCancelled is called on active token', () => {
    const token = new CancellationTokenImpl()
    
    expect(() => token.throwIfCancelled()).not.toThrow()
  })
})

describe('createCancellationToken', () => {
  it('should create a new cancellation token', () => {
    const token = createCancellationToken()
    
    expect(token.isCancelled).toBe(false)
    expect(typeof token.cancel).toBe('function')
    expect(typeof token.throwIfCancelled).toBe('function')
    expect(typeof token.onCancelled).toBe('function')
  })
})

describe('createTimeoutToken', () => {
  it('should cancel after timeout', async () => {
    vi.useFakeTimers()
    
    const token = createTimeoutToken(1000)
    
    expect(token.isCancelled).toBe(false)
    
    vi.advanceTimersByTime(1000)
    
    expect(token.isCancelled).toBe(true)
    
    vi.useRealTimers()
  })
})

describe('combineCancellationTokens', () => {
  it('should cancel when any token cancels', () => {
    const token1 = createCancellationToken()
    const token2 = createCancellationToken()
    const combined = combineCancellationTokens(token1, token2)
    
    expect(combined.isCancelled).toBe(false)
    
    token1.cancel()
    
    expect(combined.isCancelled).toBe(true)
  })

  it('should be cancelled immediately if any input is cancelled', () => {
    const token1 = createCancellationToken()
    const token2 = createCancellationToken()
    
    token1.cancel()
    
    const combined = combineCancellationTokens(token1, token2)
    
    expect(combined.isCancelled).toBe(true)
  })

  it('should handle empty input', () => {
    const combined = combineCancellationTokens()
    
    expect(combined.isCancelled).toBe(false)
  })
})

describe('raceWithCancellation', () => {
  it('should resolve with operation result when operation completes first', async () => {
    const token = createCancellationToken()
    const operation = Promise.resolve('success')
    
    const result = await raceWithCancellation(operation, token)
    
    expect(result).toBe('success')
  })

  it('should reject with cancellation when token cancels first', async () => {
    const token = createCancellationToken()
    const operation = new Promise(resolve => setTimeout(resolve, 1000))
    
    token.cancel()
    
    await expect(raceWithCancellation(operation, token)).rejects.toThrow(CancellationError)
  })

  it('should reject immediately if token is already cancelled', async () => {
    const token = createCancellationToken()
    token.cancel()
    
    const operation = Promise.resolve('success')
    
    await expect(raceWithCancellation(operation, token)).rejects.toThrow(CancellationError)
  })

  it('should reject with operation error when operation fails first', async () => {
    const token = createCancellationToken()
    const operation = Promise.reject(new Error('operation failed'))
    
    await expect(raceWithCancellation(operation, token)).rejects.toThrow('operation failed')
  })

  it('should handle cancellation during operation', async () => {
    vi.useFakeTimers()
    
    const token = createCancellationToken()
    const operation = new Promise(resolve => setTimeout(() => resolve('success'), 1000))
    
    const promise = raceWithCancellation(operation, token)
    
    // Cancel after 500ms
    vi.advanceTimersByTime(500)
    token.cancel()
    
    await expect(promise).rejects.toThrow(CancellationError)
    
    vi.useRealTimers()
  })
})

describe('CancellationError', () => {
  it('should create error with default message', () => {
    const error = new CancellationError()
    
    expect(error.name).toBe('CancellationError')
    expect(error.message).toBe('Operation was cancelled')
  })

  it('should create error with custom message', () => {
    const error = new CancellationError('Custom cancellation')
    
    expect(error.name).toBe('CancellationError')
    expect(error.message).toBe('Custom cancellation')
  })
})