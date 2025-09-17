/**
 * Concurrency Limiter
 * 
 * Limits the number of concurrent operations and provides queueing
 * with configurable strategies for handling queue overflow.
 */

import type { ConcurrencyLimiterConfig, CancellationToken } from '../types'
import { CancellationError } from './cancellation'

interface QueuedOperation<T> {
  operation: () => Promise<T>
  resolve: (value: T) => void
  reject: (error: Error) => void
  cancellationToken?: CancellationToken
}

export class ConcurrencyLimiter {
  private readonly config: ConcurrencyLimiterConfig
  private running = 0
  private queue: QueuedOperation<unknown>[] = []

  constructor(config: ConcurrencyLimiterConfig) {
    this.config = config
  }

  /**
   * Execute an operation with concurrency limiting
   */
  async execute<T>(
    operation: () => Promise<T>,
    cancellationToken?: CancellationToken
  ): Promise<T> {
    return new Promise<T>((resolve, reject) => {
      // Check if cancelled before queuing
      if (cancellationToken?.isCancelled) {
        reject(new CancellationError())
        return
      }

      const queuedOp: QueuedOperation<T> = {
        operation,
        resolve,
        reject,
        cancellationToken
      }

      // If we can run immediately, do so
      if (this.running < this.config.maxConcurrent) {
        this.executeImmediate(queuedOp)
        return
      }

      // Otherwise, queue it
      if (this.queue.length >= this.config.queueLimit) {
        reject(new Error('Concurrency queue is full'))
        return
      }

      this.queue.push(queuedOp)

      // Set up cancellation handler for queued operation
      cancellationToken?.onCancelled(() => {
        const index = this.queue.indexOf(queuedOp)
        if (index >= 0) {
          this.queue.splice(index, 1)
          reject(new CancellationError())
        }
      })
    })
  }

  /**
   * Get current stats about the limiter
   */
  getStats() {
    return {
      running: this.running,
      queued: this.queue.length,
      maxConcurrent: this.config.maxConcurrent,
      queueLimit: this.config.queueLimit
    }
  }

  /**
   * Execute an operation immediately (no queueing)
   */
  private async executeImmediate<T>(queuedOp: QueuedOperation<T>): Promise<void> {
    this.running++

    try {
      // Check cancellation before starting
      if (queuedOp.cancellationToken?.isCancelled) {
        queuedOp.reject(new CancellationError())
        return
      }

      const result = await queuedOp.operation()
      queuedOp.resolve(result)
    } catch (error) {
      queuedOp.reject(error instanceof Error ? error : new Error(String(error)))
    } finally {
      this.running--
      this.processQueue()
    }
  }

  /**
   * Process the next item in the queue if possible
   */
  private processQueue(): void {
    if (this.running >= this.config.maxConcurrent || this.queue.length === 0) {
      return
    }

    const nextOp = this.queue.shift()
    if (nextOp) {
      this.executeImmediate(nextOp)
    }
  }
}

/**
 * Create a concurrency limiter with default config
 */
export function createConcurrencyLimiter(
  config: Partial<ConcurrencyLimiterConfig> = {}
): ConcurrencyLimiter {
  const defaultConfig: ConcurrencyLimiterConfig = {
    maxConcurrent: 5,
    queueLimit: 20
  }
  
  return new ConcurrencyLimiter({ ...defaultConfig, ...config })
}

/**
 * A simple semaphore implementation for resource limiting
 */
export class Semaphore {
  private permits: number
  private waitQueue: Array<() => void> = []

  constructor(permits: number) {
    this.permits = permits
  }

  /**
   * Acquire a permit (async)
   */
  async acquire(): Promise<void> {
    return new Promise<void>((resolve) => {
      if (this.permits > 0) {
        this.permits--
        resolve()
      } else {
        this.waitQueue.push(resolve)
      }
    })
  }

  /**
   * Release a permit
   */
  release(): void {
    if (this.waitQueue.length > 0) {
      const next = this.waitQueue.shift()!
      next()
    } else {
      this.permits++
    }
  }

  /**
   * Try to acquire a permit synchronously
   */
  tryAcquire(): boolean {
    if (this.permits > 0) {
      this.permits--
      return true
    }
    return false
  }

  /**
   * Get current available permits
   */
  availablePermits(): number {
    return this.permits
  }
}