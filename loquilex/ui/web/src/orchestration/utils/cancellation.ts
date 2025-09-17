/**
 * Cancellation Token Implementation
 * 
 * Provides cooperative cancellation patterns for async operations.
 */

import type { CancellationToken } from '../types'

export class CancellationTokenImpl implements CancellationToken {
  private _isCancelled = false
  private _callbacks: Array<() => void> = []

  get isCancelled(): boolean {
    return this._isCancelled
  }

  cancel(): void {
    if (this._isCancelled) return
    
    this._isCancelled = true
    
    // Execute all registered callbacks
    for (const callback of this._callbacks) {
      try {
        callback()
      } catch (error) {
        // Log but don't throw - cancellation should not fail
        console.warn('Error in cancellation callback:', error)
      }
    }
    
    // Clear callbacks to prevent memory leaks
    this._callbacks.length = 0
  }

  throwIfCancelled(): void {
    if (this._isCancelled) {
      throw new CancellationError('Operation was cancelled')
    }
  }

  onCancelled(callback: () => void): void {
    if (this._isCancelled) {
      // If already cancelled, execute immediately
      try {
        callback()
      } catch (error) {
        console.warn('Error in immediate cancellation callback:', error)
      }
      return
    }
    
    this._callbacks.push(callback)
  }
}

export class CancellationError extends Error {
  constructor(message = 'Operation was cancelled') {
    super(message)
    this.name = 'CancellationError'
  }
}

/**
 * Create a new cancellation token
 */
export function createCancellationToken(): CancellationToken {
  return new CancellationTokenImpl()
}

/**
 * Create a cancellation token that automatically cancels after a timeout
 */
export function createTimeoutToken(timeoutMs: number): CancellationToken {
  const token = new CancellationTokenImpl()
  
  setTimeout(() => {
    token.cancel()
  }, timeoutMs)
  
  return token
}

/**
 * Combine multiple cancellation tokens - cancels when any of them cancel
 */
export function combineCancellationTokens(
  ...tokens: CancellationToken[]
): CancellationToken {
  const combined = new CancellationTokenImpl()
  
  for (const token of tokens) {
    if (token.isCancelled) {
      combined.cancel()
      return combined
    }
    
    token.onCancelled(() => combined.cancel())
  }
  
  return combined
}

/**
 * Race an async operation against a cancellation token
 */
export async function raceWithCancellation<T>(
  operation: Promise<T>,
  cancellationToken: CancellationToken
): Promise<T> {
  if (cancellationToken.isCancelled) {
    throw new CancellationError()
  }
  
  return new Promise<T>((resolve, reject) => {
    let completed = false
    
    // Handle operation completion
    operation
      .then((result) => {
        if (!completed) {
          completed = true
          resolve(result)
        }
      })
      .catch((error) => {
        if (!completed) {
          completed = true
          reject(error)
        }
      })
    
    // Handle cancellation
    cancellationToken.onCancelled(() => {
      if (!completed) {
        completed = true
        reject(new CancellationError())
      }
    })
  })
}