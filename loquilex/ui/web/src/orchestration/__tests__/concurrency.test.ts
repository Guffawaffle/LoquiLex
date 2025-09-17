/**
 * Unit tests for concurrency utilities
 */

import { describe, it, expect, vi } from 'vitest'
import {
  ConcurrencyLimiter,
  createConcurrencyLimiter,
  Semaphore
} from '../utils/concurrency'
import { createCancellationToken } from '../utils/cancellation'

describe('ConcurrencyLimiter', () => {
  it('should execute operations immediately when under limit', async () => {
    const limiter = new ConcurrencyLimiter({ maxConcurrent: 2, queueLimit: 10 })
    const operation = vi.fn().mockResolvedValue('result')
    
    const result = await limiter.execute(operation)
    
    expect(result).toBe('result')
    expect(operation).toHaveBeenCalledTimes(1)
  })

  it('should queue operations when at limit', async () => {
    const limiter = new ConcurrencyLimiter({ maxConcurrent: 1, queueLimit: 10 })
    let resolveFirst: (value: string) => void
    
    const firstOperation = vi.fn().mockImplementation(() => 
      new Promise<string>(resolve => { resolveFirst = resolve })
    )
    const secondOperation = vi.fn().mockResolvedValue('second')
    
    // Start first operation (should execute immediately)
    const firstPromise = limiter.execute(firstOperation)
    
    // Start second operation (should be queued)
    const secondPromise = limiter.execute(secondOperation)
    
    // First should be running, second should be queued
    expect(limiter.getStats().running).toBe(1)
    expect(limiter.getStats().queued).toBe(1)
    expect(secondOperation).not.toHaveBeenCalled()
    
    // Complete first operation
    resolveFirst!('first')
    await firstPromise
    
    // Now second should execute
    await secondPromise
    expect(secondOperation).toHaveBeenCalledTimes(1)
  })

  it('should reject when queue is full', async () => {
    const limiter = new ConcurrencyLimiter({ maxConcurrent: 1, queueLimit: 1 })
    let resolveFirst: (value: string) => void
    
    const operation = () => new Promise<string>(resolve => { resolveFirst = resolve })
    
    // Fill up concurrent slot
    limiter.execute(operation)
    
    // Fill up queue
    limiter.execute(operation)
    
    // This should be rejected
    await expect(limiter.execute(operation)).rejects.toThrow('Concurrency queue is full')
  })

  it('should handle operation errors', async () => {
    const limiter = new ConcurrencyLimiter({ maxConcurrent: 1, queueLimit: 10 })
    const operation = vi.fn().mockRejectedValue(new Error('operation failed'))
    
    await expect(limiter.execute(operation)).rejects.toThrow('operation failed')
    
    // Should be able to execute more operations after error
    const successOperation = vi.fn().mockResolvedValue('success')
    const result = await limiter.execute(successOperation)
    expect(result).toBe('success')
  })

  it('should respect cancellation tokens', async () => {
    const limiter = new ConcurrencyLimiter({ maxConcurrent: 1, queueLimit: 10 })
    const token = createCancellationToken()
    
    // Block the limiter with a long-running operation
    let resolveFirst: (value: string) => void
    const blockingOperation = () => new Promise<string>(resolve => { resolveFirst = resolve })
    limiter.execute(blockingOperation)
    
    // Queue an operation with cancellation token
    const operation = vi.fn().mockResolvedValue('result')
    const promise = limiter.execute(operation, token)
    
    // Cancel the token
    token.cancel()
    
    await expect(promise).rejects.toThrow('Operation was cancelled')
    
    // Operation should never have been called
    expect(operation).not.toHaveBeenCalled()
    
    // Queue should be empty
    expect(limiter.getStats().queued).toBe(0)
  })

  it('should provide accurate stats', () => {
    const limiter = new ConcurrencyLimiter({ maxConcurrent: 2, queueLimit: 5 })
    
    const stats = limiter.getStats()
    
    expect(stats.running).toBe(0)
    expect(stats.queued).toBe(0)
    expect(stats.maxConcurrent).toBe(2)
    expect(stats.queueLimit).toBe(5)
  })
})

describe('createConcurrencyLimiter', () => {
  it('should create limiter with default config', () => {
    const limiter = createConcurrencyLimiter()
    
    const stats = limiter.getStats()
    expect(stats.maxConcurrent).toBe(5)
    expect(stats.queueLimit).toBe(20)
  })

  it('should create limiter with custom config', () => {
    const limiter = createConcurrencyLimiter({ maxConcurrent: 10 })
    
    const stats = limiter.getStats()
    expect(stats.maxConcurrent).toBe(10)
    expect(stats.queueLimit).toBe(20) // Default
  })
})

describe('Semaphore', () => {
  it('should allow acquisition up to permit limit', async () => {
    const semaphore = new Semaphore(2)
    
    expect(semaphore.availablePermits()).toBe(2)
    
    await semaphore.acquire()
    expect(semaphore.availablePermits()).toBe(1)
    
    await semaphore.acquire()
    expect(semaphore.availablePermits()).toBe(0)
  })

  it('should block when no permits available', async () => {
    const semaphore = new Semaphore(1)
    
    // Acquire the only permit
    await semaphore.acquire()
    
    let acquired = false
    const acquisition = semaphore.acquire().then(() => { acquired = true })
    
    // Should not acquire immediately
    await new Promise(resolve => setTimeout(resolve, 0))
    expect(acquired).toBe(false)
    
    // Release permit
    semaphore.release()
    
    // Now should acquire
    await acquisition
    expect(acquired).toBe(true)
  })

  it('should support tryAcquire', () => {
    const semaphore = new Semaphore(1)
    
    expect(semaphore.tryAcquire()).toBe(true)
    expect(semaphore.availablePermits()).toBe(0)
    
    expect(semaphore.tryAcquire()).toBe(false)
    expect(semaphore.availablePermits()).toBe(0)
  })

  it('should release permits correctly', () => {
    const semaphore = new Semaphore(1)
    
    semaphore.tryAcquire()
    expect(semaphore.availablePermits()).toBe(0)
    
    semaphore.release()
    expect(semaphore.availablePermits()).toBe(1)
  })

  it('should handle queue on release', async () => {
    const semaphore = new Semaphore(1)
    
    // Acquire the permit
    await semaphore.acquire()
    
    // Start waiting for permit
    let acquired = false
    const acquisition = semaphore.acquire().then(() => { acquired = true })
    
    // Release should unblock the waiting acquisition
    semaphore.release()
    
    await acquisition
    expect(acquired).toBe(true)
    expect(semaphore.availablePermits()).toBe(0) // Permit was immediately taken
  })
})