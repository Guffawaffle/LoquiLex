/**
 * Store Helpers and State Machine Utilities
 * 
 * Provides helper functions and utilities for managing Zustand stores
 * and state machine patterns.
 */

import type { 
  AsyncOperation, 
  AsyncOperationState, 
  StoreAction 
} from '../types'

/**
 * Create an initial async operation state
 */
export function createAsyncOperation<T = unknown>(): AsyncOperation<T> {
  return {
    state: 'idle'
  }
}

/**
 * Create a pending async operation
 */
export function createPendingOperation<T = unknown>(startTime?: number): AsyncOperation<T> {
  return {
    state: 'pending',
    startTime: startTime ?? Date.now()
  }
}

/**
 * Create a successful async operation
 */
export function createSuccessOperation<T>(data: T, startTime?: number): AsyncOperation<T> {
  const now = Date.now()
  return {
    state: 'success',
    data,
    startTime,
    endTime: now
  }
}

/**
 * Create a failed async operation
 */
export function createErrorOperation<T = unknown>(
  error: Error, 
  startTime?: number
): AsyncOperation<T> {
  const now = Date.now()
  return {
    state: 'error',
    error,
    startTime,
    endTime: now
  }
}

/**
 * Create a cancelled async operation
 */
export function createCancelledOperation<T = unknown>(
  startTime?: number
): AsyncOperation<T> {
  const now = Date.now()
  return {
    state: 'cancelled',
    startTime,
    endTime: now
  }
}

/**
 * Update an async operation's state
 */
export function updateOperationState<T>(
  operation: AsyncOperation<T>,
  newState: AsyncOperationState,
  data?: T,
  error?: Error
): AsyncOperation<T> {
  const now = Date.now()
  
  switch (newState) {
    case 'pending':
      return {
        ...operation,
        state: 'pending',
        startTime: operation.startTime ?? now,
        data: undefined,
        error: undefined,
        endTime: undefined
      }
      
    case 'success':
      return {
        ...operation,
        state: 'success',
        data,
        error: undefined,
        endTime: now
      }
      
    case 'error':
      return {
        ...operation,
        state: 'error',
        error,
        data: undefined,
        endTime: now
      }
      
    case 'cancelled':
      return {
        ...operation,
        state: 'cancelled',
        endTime: now
      }
      
    default:
      return {
        ...operation,
        state: newState
      }
  }
}

/**
 * Check if an operation is in a terminal state
 */
export function isTerminalState(state: AsyncOperationState): boolean {
  return state === 'success' || state === 'error' || state === 'cancelled'
}

/**
 * Check if an operation is loading
 */
export function isLoading(operation: AsyncOperation): boolean {
  return operation.state === 'pending'
}

/**
 * Check if an operation was successful
 */
export function isSuccess(operation: AsyncOperation): boolean {
  return operation.state === 'success'
}

/**
 * Check if an operation failed
 */
export function isError(operation: AsyncOperation): boolean {
  return operation.state === 'error'
}

/**
 * Get operation duration in milliseconds
 */
export function getOperationDuration(operation: AsyncOperation): number | undefined {
  if (!operation.startTime) return undefined
  const endTime = operation.endTime ?? Date.now()
  return endTime - operation.startTime
}

/**
 * Create a store action with metadata
 */
export function createAction<T = unknown>(
  type: string, 
  payload?: T,
  correlationId?: string
): StoreAction<T> {
  return {
    type,
    payload,
    meta: {
      timestamp: Date.now(),
      correlationId
    }
  }
}

/**
 * Generic async operation reducer
 */
export function asyncOperationReducer<T>(
  state: AsyncOperation<T>,
  action: StoreAction
): AsyncOperation<T> {
  const { type, payload } = action
  
  if (type.endsWith('/pending')) {
    return updateOperationState(state, 'pending')
  }
  
  if (type.endsWith('/fulfilled')) {
    return updateOperationState(state, 'success', payload as T)
  }
  
  if (type.endsWith('/rejected')) {
    return updateOperationState(state, 'error', undefined, payload as Error)
  }
  
  if (type.endsWith('/cancelled')) {
    return updateOperationState(state, 'cancelled')
  }
  
  return state
}

/**
 * Create a Zustand store slice for async operations
 */
export function createAsyncSlice<T, TPayload = unknown>(
  name: string,
  asyncFn: (payload: TPayload) => Promise<T>
) {
  const initialState = createAsyncOperation<T>()
  
  return {
    // State
    [name]: initialState,
    
    // Actions
    [`${name}Async`]: async (payload: TPayload) => {
      const startAction = createAction(`${name}/pending`)
      
      try {
        // This would be used within a Zustand store setter
        // The actual implementation depends on how it's integrated
        const result = await asyncFn(payload)
        const successAction = createAction(`${name}/fulfilled`, result)
        return result
      } catch (error) {
        const errorAction = createAction(`${name}/rejected`, error)
        throw error
      }
    },
    
    // Selectors
    [`${name}Loading`]: (state: any) => isLoading(state[name]),
    [`${name}Data`]: (state: any) => state[name].data,
    [`${name}Error`]: (state: any) => state[name].error,
  }
}

/**
 * Debounce utility for store updates
 */
export function createDebouncer(delayMs = 300) {
  let timeoutId: number | null = null
  
  return function debounce<T extends (...args: any[]) => any>(fn: T): T {
    return ((...args: Parameters<T>) => {
      if (timeoutId !== null) {
        clearTimeout(timeoutId)
      }
      
      timeoutId = window.setTimeout(() => {
        timeoutId = null
        fn(...args)
      }, delayMs)
    }) as T
  }
}

/**
 * Throttle utility for high-frequency updates
 */
export function createThrottler(intervalMs = 100) {
  let lastCall = 0
  let timeoutId: number | null = null
  
  return function throttle<T extends (...args: any[]) => any>(fn: T): T {
    return ((...args: Parameters<T>) => {
      const now = Date.now()
      
      if (now - lastCall >= intervalMs) {
        lastCall = now
        fn(...args)
      } else {
        // Schedule for later if not already scheduled
        if (timeoutId === null) {
          timeoutId = window.setTimeout(() => {
            timeoutId = null
            lastCall = Date.now()
            fn(...args)
          }, intervalMs - (now - lastCall))
        }
      }
    }) as T
  }
}

/**
 * Create a selector that memoizes based on dependencies
 */
export function createSelector<TState, TResult>(
  selector: (state: TState) => TResult,
  equalityFn?: (a: TResult, b: TResult) => boolean
) {
  let lastState: TState
  let lastResult: TResult
  let hasResult = false
  
  return (state: TState): TResult => {
    if (!hasResult || state !== lastState) {
      const newResult = selector(state)
      
      if (!hasResult || !equalityFn?.(lastResult, newResult)) {
        lastResult = newResult
        hasResult = true
      }
    }
    
    lastState = state
    return lastResult
  }
}