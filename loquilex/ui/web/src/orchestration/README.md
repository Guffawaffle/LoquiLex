# Orchestration Module

A comprehensive **JS-first** orchestration layer for React/TypeScript applications providing shared utilities, strict type contracts, and Web Worker support.

## Features

- **🔄 Retry & Backoff**: Configurable retry logic with exponential backoff and jitter
- **🚫 Cancellation**: Cooperative cancellation tokens for async operations
- **🎯 Concurrency**: Limiter with queuing and backpressure handling
- **📨 WebSocket Client**: Robust WS client with auto-reconnect and message typing
- **⚡ Web Workers**: Progress smoothing and ETA computation off main thread
- **🏪 Store Utilities**: Zustand helpers and state machine patterns
- **📋 Bounded Queues**: Thread-safe queues with configurable drop strategies
- **💾 TypeScript Strict**: Full type safety with strict mode compliance

## Installation

The orchestration module is part of the LoquiLex UI package. Import what you need:

```typescript
import {
  withRetry,
  createCancellationToken,
  createConcurrencyLimiter,
  createWSClient,
  createProgressWorker
} from '@/orchestration'
```

## Quick Start

### Basic Retry with Cancellation

```typescript
import { withRetry, createCancellationToken } from '@/orchestration'

const token = createCancellationToken()
const result = await withRetry(
  async () => {
    const response = await fetch('/api/data')
    if (!response.ok) throw new Error('API failed')
    return response.json()
  },
  { maxAttempts: 3, initialDelay: 1000 },
  token
)
```

### Concurrency Limiting

```typescript
import { createConcurrencyLimiter } from '@/orchestration'

const limiter = createConcurrencyLimiter({ maxConcurrent: 3, queueLimit: 10 })

// All operations will be limited to 3 concurrent executions
const results = await Promise.all([
  limiter.execute(() => downloadFile('file1.zip')),
  limiter.execute(() => downloadFile('file2.zip')),
  limiter.execute(() => downloadFile('file3.zip')),
  limiter.execute(() => downloadFile('file4.zip')) // Queued
])
```

### WebSocket Client

```typescript
import { createWSClient } from '@/orchestration'

const client = createWSClient('ws://localhost:8000/ws', {
  onMessage: (envelope) => {
    console.log('Received:', envelope.t, envelope.data)
  },
  onStateChange: (state) => {
    console.log('Connection state:', state)
  }
})

await client.connect()

// Send typed messages
client.send('session.hello', { clientInfo: 'browser' })
```

### Progress Smoothing with Web Workers

```typescript
import { ProgressSmoother } from '@/orchestration'

const smoother = new ProgressSmoother()
await smoother.initialize()

// Add progress samples (typically from download callbacks)
const result = await smoother.addSample(0.45) // 45% complete

console.log({
  smoothed: result.smoothedProgress, // Smoothed to prevent UI jank
  rate: result.rate,                // Progress per second
  eta: result.eta                   // Estimated time remaining
})
```

### Store Helpers

```typescript
import { create } from 'zustand'
import { 
  createAsyncOperation, 
  createPendingOperation,
  createSuccessOperation,
  isLoading 
} from '@/orchestration'

interface State {
  download: AsyncOperation<DownloadResult>
  startDownload: (url: string) => Promise<void>
}

const useStore = create<State>((set) => ({
  download: createAsyncOperation(),
  
  async startDownload(url: string) {
    set({ download: createPendingOperation() })
    
    try {
      const result = await downloadFile(url)
      set({ download: createSuccessOperation(result) })
    } catch (error) {
      set({ download: createErrorOperation(error) })
    }
  }
}))

// In component
const { download, startDownload } = useStore()
const isDownloading = isLoading(download)
```

## API Reference

### Types

- `AsyncOperation<T>` - State machine for async operations
- `CancellationToken` - Cooperative cancellation interface
- `WSEnvelope<T>` - Typed WebSocket message envelope
- `RetryConfig` - Configuration for retry behavior
- `ConcurrencyLimiterConfig` - Configuration for concurrency limiting

### Utilities

- `withRetry()` - Execute with exponential backoff retry
- `createCancellationToken()` - Create cancellation token
- `createTimeoutToken()` - Auto-cancelling timeout token
- `combineCancellationTokens()` - Combine multiple tokens
- `createConcurrencyLimiter()` - Limit concurrent operations
- `createBoundedQueue()` - Thread-safe bounded queue

### Client

- `createWSClient()` - Robust WebSocket client
- `WSClient#connect()` - Connect with auto-retry
- `WSClient#send()` - Send typed messages
- `WSClient#disconnect()` - Clean disconnect

### Workers

- `createProgressWorker()` - Progress computation worker
- `ProgressSmoother` - High-level progress smoother
- `WorkerChannel` - Generic worker communication

### Store Helpers

- `createAsyncOperation()` - Initial operation state
- `updateOperationState()` - State transitions
- `isLoading()`, `isSuccess()`, `isError()` - State predicates
- `createDebouncer()`, `createThrottler()` - Rate limiting
- `createSelector()` - Memoized selectors

## Examples

See the `examples/` directory for complete implementations:

- `downloads-store.ts` - Full downloads orchestrator with Zustand
- `progress-demo.tsx` - Interactive progress smoothing demo

## Testing

The module includes comprehensive unit tests with >80% coverage:

```bash
npm run test src/orchestration/__tests__
```

Test files cover:
- Retry logic and backoff calculation
- Cancellation token behavior
- Concurrency limiting and queueing
- Bounded queue drop strategies
- Store helpers and state machines

## Configuration Defaults

```typescript
const DEFAULT_CONFIGS = {
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
    dropStrategy: 'oldest'
  }
}
```

## Browser Compatibility

- Modern browsers with ES2020 support
- Web Workers support required for progress smoothing
- WebSocket support required for WS client

## Architecture Notes

This orchestration layer is designed to be:

- **Framework agnostic**: Core utilities work with any framework
- **Type-safe**: Strict TypeScript with exact optional property types
- **Testable**: Comprehensive mocking and dependency injection
- **Performant**: Web Workers for heavy computation, bounded queues for memory safety
- **Resilient**: Built-in retry, backoff, and error handling patterns

The module follows the **actor model** for concurrency and provides **reactive patterns** for state management while maintaining **functional programming** principles where possible.