/**
 * Unit tests for store helpers and utilities
 */

import { describe, it, expect, vi } from 'vitest'
import {
  createAsyncOperation,
  createPendingOperation,
  createSuccessOperation,
  createErrorOperation,
  createCancelledOperation,
  updateOperationState,
  isTerminalState,
  isLoading,
  isSuccess,
  isError,
  getOperationDuration,
  createAction,
  asyncOperationReducer,
  createDebouncer,
  createThrottler,
  createSelector
} from '../store/helpers'

describe('async operation creators', () => {
  it('should create initial operation', () => {
    const op = createAsyncOperation()
    
    expect(op.state).toBe('idle')
    expect(op.data).toBeUndefined()
    expect(op.error).toBeUndefined()
  })

  it('should create pending operation', () => {
    const startTime = Date.now()
    const op = createPendingOperation(startTime)
    
    expect(op.state).toBe('pending')
    expect(op.startTime).toBe(startTime)
  })

  it('should create success operation', () => {
    const data = { result: 'test' }
    const startTime = Date.now() - 1000
    const op = createSuccessOperation(data, startTime)
    
    expect(op.state).toBe('success')
    expect(op.data).toBe(data)
    expect(op.startTime).toBe(startTime)
    expect(op.endTime).toBeGreaterThan(startTime)
  })

  it('should create error operation', () => {
    const error = new Error('test error')
    const startTime = Date.now() - 1000
    const op = createErrorOperation(error, startTime)
    
    expect(op.state).toBe('error')
    expect(op.error).toBe(error)
    expect(op.startTime).toBe(startTime)
    expect(op.endTime).toBeGreaterThan(startTime)
  })

  it('should create cancelled operation', () => {
    const startTime = Date.now() - 1000
    const op = createCancelledOperation(startTime)
    
    expect(op.state).toBe('cancelled')
    expect(op.startTime).toBe(startTime)
    expect(op.endTime).toBeGreaterThan(startTime)
  })
})

describe('updateOperationState', () => {
  it('should transition to pending state', () => {
    const initial = createAsyncOperation()
    const updated = updateOperationState(initial, 'pending')
    
    expect(updated.state).toBe('pending')
    expect(updated.startTime).toBeGreaterThan(0)
    expect(updated.data).toBeUndefined()
    expect(updated.error).toBeUndefined()
  })

  it('should transition to success state', () => {
    const pending = createPendingOperation()
    const data = { result: 'success' }
    const updated = updateOperationState(pending, 'success', data)
    
    expect(updated.state).toBe('success')
    expect(updated.data).toBe(data)
    expect(updated.error).toBeUndefined()
    expect(updated.endTime).toBeGreaterThan(0)
  })

  it('should transition to error state', () => {
    const pending = createPendingOperation()
    const error = new Error('failed')
    const updated = updateOperationState(pending, 'error', undefined, error)
    
    expect(updated.state).toBe('error')
    expect(updated.error).toBe(error)
    expect(updated.data).toBeUndefined()
    expect(updated.endTime).toBeGreaterThan(0)
  })
})

describe('state predicates', () => {
  it('should identify terminal states', () => {
    expect(isTerminalState('success')).toBe(true)
    expect(isTerminalState('error')).toBe(true)
    expect(isTerminalState('cancelled')).toBe(true)
    expect(isTerminalState('pending')).toBe(false)
    expect(isTerminalState('idle')).toBe(false)
  })

  it('should identify loading state', () => {
    expect(isLoading(createPendingOperation())).toBe(true)
    expect(isLoading(createAsyncOperation())).toBe(false)
    expect(isLoading(createSuccessOperation('data'))).toBe(false)
  })

  it('should identify success state', () => {
    expect(isSuccess(createSuccessOperation('data'))).toBe(true)
    expect(isSuccess(createPendingOperation())).toBe(false)
    expect(isSuccess(createErrorOperation(new Error()))).toBe(false)
  })

  it('should identify error state', () => {
    expect(isError(createErrorOperation(new Error()))).toBe(true)
    expect(isError(createSuccessOperation('data'))).toBe(false)
    expect(isError(createPendingOperation())).toBe(false)
  })
})

describe('getOperationDuration', () => {
  it('should return undefined for operations without start time', () => {
    const op = createAsyncOperation()
    expect(getOperationDuration(op)).toBeUndefined()
  })

  it('should calculate duration for completed operations', () => {
    const startTime = Date.now() - 1000
    const op = createSuccessOperation('data', startTime)
    const duration = getOperationDuration(op)
    
    expect(duration).toBeGreaterThanOrEqual(1000)
  })

  it('should calculate duration for ongoing operations', () => {
    const startTime = Date.now() - 500
    const op = createPendingOperation(startTime)
    const duration = getOperationDuration(op)
    
    expect(duration).toBeGreaterThanOrEqual(500)
  })
})

describe('createAction', () => {
  it('should create action with type and payload', () => {
    const payload = { data: 'test' }
    const action = createAction('TEST_ACTION', payload)
    
    expect(action.type).toBe('TEST_ACTION')
    expect(action.payload).toBe(payload)
    expect(action.meta?.timestamp).toBeGreaterThan(0)
  })

  it('should create action with correlation ID', () => {
    const action = createAction('TEST_ACTION', null, 'corr-123')
    
    expect(action.meta?.correlationId).toBe('corr-123')
  })
})

describe('asyncOperationReducer', () => {
  it('should handle pending action', () => {
    const state = createAsyncOperation()
    const action = createAction('test/pending')
    const newState = asyncOperationReducer(state, action)
    
    expect(newState.state).toBe('pending')
  })

  it('should handle fulfilled action', () => {
    const state = createPendingOperation()
    const payload = { result: 'success' }
    const action = createAction('test/fulfilled', payload)
    const newState = asyncOperationReducer(state, action)
    
    expect(newState.state).toBe('success')
    expect(newState.data).toBe(payload)
  })

  it('should handle rejected action', () => {
    const state = createPendingOperation()
    const error = new Error('failed')
    const action = createAction('test/rejected', error)
    const newState = asyncOperationReducer(state, action)
    
    expect(newState.state).toBe('error')
    expect(newState.error).toBe(error)
  })

  it('should handle cancelled action', () => {
    const state = createPendingOperation()
    const action = createAction('test/cancelled')
    const newState = asyncOperationReducer(state, action)
    
    expect(newState.state).toBe('cancelled')
  })

  it('should ignore unknown actions', () => {
    const state = createPendingOperation()
    const action = createAction('OTHER_ACTION')
    const newState = asyncOperationReducer(state, action)
    
    expect(newState).toBe(state)
  })
})

describe('createDebouncer', () => {
  beforeEach(() => {
    vi.useFakeTimers()
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('should debounce function calls', () => {
    const fn = vi.fn()
    const debouncedFn = createDebouncer(100)(fn)
    
    debouncedFn()
    debouncedFn()
    debouncedFn()
    
    expect(fn).not.toHaveBeenCalled()
    
    vi.advanceTimersByTime(100)
    
    expect(fn).toHaveBeenCalledTimes(1)
  })

  it('should reset timer on subsequent calls', () => {
    const fn = vi.fn()
    const debouncedFn = createDebouncer(100)(fn)
    
    debouncedFn()
    vi.advanceTimersByTime(50)
    
    debouncedFn() // Should reset timer
    vi.advanceTimersByTime(50)
    
    expect(fn).not.toHaveBeenCalled()
    
    vi.advanceTimersByTime(50)
    
    expect(fn).toHaveBeenCalledTimes(1)
  })
})

describe('createThrottler', () => {
  beforeEach(() => {
    vi.useFakeTimers()
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('should throttle function calls', () => {
    const fn = vi.fn()
    const throttledFn = createThrottler(100)(fn)
    
    throttledFn() // Should execute immediately
    expect(fn).toHaveBeenCalledTimes(1)
    
    throttledFn() // Should be throttled
    throttledFn() // Should be throttled
    
    expect(fn).toHaveBeenCalledTimes(1)
    
    vi.advanceTimersByTime(100)
    
    expect(fn).toHaveBeenCalledTimes(2) // Scheduled call should execute
  })
})

describe('createSelector', () => {
  it('should memoize selector results', () => {
    const selectorFn = vi.fn((state: { value: number }) => state.value * 2)
    const selector = createSelector(selectorFn)
    
    const state1 = { value: 5 }
    const result1 = selector(state1)
    const result2 = selector(state1) // Same state
    
    expect(result1).toBe(10)
    expect(result2).toBe(10)
    expect(selectorFn).toHaveBeenCalledTimes(1) // Should be memoized
  })

  it('should recalculate when state changes', () => {
    const selectorFn = vi.fn((state: { value: number }) => state.value * 2)
    const selector = createSelector(selectorFn)
    
    const state1 = { value: 5 }
    const state2 = { value: 10 }
    
    const result1 = selector(state1)
    const result2 = selector(state2)
    
    expect(result1).toBe(10)
    expect(result2).toBe(20)
    expect(selectorFn).toHaveBeenCalledTimes(2)
  })

  it('should use custom equality function', () => {
    const selectorFn = vi.fn((state: { items: string[] }) => state.items.join(','))
    const equalityFn = vi.fn((a: string, b: string) => a === b)
    const selector = createSelector(selectorFn, equalityFn)
    
    const state1 = { items: ['a', 'b'] }
    const state2 = { items: ['a', 'b'] } // Different object, same content
    
    selector(state1)
    selector(state2)
    
    expect(selectorFn).toHaveBeenCalledTimes(2) // Called for both states
    expect(equalityFn).toHaveBeenCalledWith('a,b', 'a,b')
  })
})