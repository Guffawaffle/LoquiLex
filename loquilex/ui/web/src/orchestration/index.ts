/**
 * Orchestration Module - Main Entry Point
 * 
 * This module provides a comprehensive orchestration layer for React/TypeScript
 * applications with shared utilities, typed contracts, and Web Worker support.
 */

// ===== Core Types =====
export * from './types'

// ===== Utilities =====
export * from './utils/retry'
export * from './utils/cancellation'
export * from './utils/concurrency'
export * from './utils/bounded-queue'
export * from './utils/throttle'

// ===== Client =====
export * from './client/ws-client'

// ===== Worker Channel =====
export * from './worker/worker-channel'

// ===== Store Helpers =====
export * from './store/helpers'

// ===== Convenience Re-exports =====

import { 
  withRetry, 
  createRetryWrapper 
} from './utils/retry'
import { 
  createCancellationToken, 
  createTimeoutToken, 
  combineCancellationTokens 
} from './utils/cancellation'
import { createConcurrencyLimiter } from './utils/concurrency'
import { createBoundedQueue } from './utils/bounded-queue'
import { createThrottler, RateLimiter } from './utils/throttle'
import { createWSClient } from './client/ws-client'
import { createProgressWorker } from './worker/worker-channel'
import { 
  createAsyncOperation,
  createPendingOperation,
  createSuccessOperation,
  createErrorOperation,
  isLoading,
  isSuccess,
  isError
} from './store/helpers'

// Re-export for convenience
export {
  withRetry,
  createRetryWrapper,
  createCancellationToken,
  createTimeoutToken,
  combineCancellationTokens,
  createConcurrencyLimiter,
  createBoundedQueue,
  createThrottler,
  RateLimiter,
  createWSClient,
  createProgressWorker,
  createAsyncOperation,
  createPendingOperation,
  createSuccessOperation,
  createErrorOperation,
  isLoading,
  isSuccess,
  isError
}

// ===== Version Information =====
export const VERSION = '1.0.0'
export const MODULE_NAME = '@/orchestration'

// ===== Default Configurations =====
export const DEFAULT_CONFIGS = {
  retry: {
    maxAttempts: 3,
    initialDelay: 1000,
    maxDelay: 30000,
    backoffMultiplier: 2,
    jitter: true
  },
  concurrency: {
    maxConcurrent: 5,
    queueLimit: 20
  },
  websocket: {
    reconnect: true,
    maxReconnectAttempts: 10,
    reconnectDelay: 1000,
    maxReconnectDelay: 30000,
    heartbeatInterval: 30000
  },
  boundedQueue: {
    maxSize: 100,
    dropStrategy: 'oldest' as const
  },
  throttle: {
    maxHz: 5,
    leading: true,
    trailing: true
  }
} as const