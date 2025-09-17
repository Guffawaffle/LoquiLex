/**
 * Worker Channel - Main thread interface to Web Workers
 * 
 * Provides a typed interface for communicating with Web Workers
 * with timeout handling and automatic cleanup.
 */

import type { 
  WorkerMessage, 
  WorkerResponse, 
  ProgressComputeRequest, 
  ProgressComputeResponse,
  CancellationToken 
} from '../types'
import { createCancellationToken, CancellationError } from '../utils/cancellation'

interface PendingRequest {
  resolve: (result: unknown) => void
  reject: (error: Error) => void
  timeout: number
}

export class WorkerChannel {
  private worker: Worker
  private nextId = 1
  private pendingRequests = new Map<string, PendingRequest>()
  private isShutdown = false

  constructor(workerScript: string | URL) {
    this.worker = new Worker(workerScript, { type: 'module' })
    this.worker.onmessage = this.handleMessage.bind(this)
    this.worker.onerror = this.handleError.bind(this)
  }

  /**
   * Initialize the worker
   */
  async initialize(): Promise<void> {
    return this.sendMessage('INIT', {}) as Promise<void>
  }

  /**
   * Compute smoothed progress with the specified target frequency
   */
  async computeProgress(
    samples: Array<{ timestamp: number; progress: number }>,
    targetHz = 5,
    cancellationToken?: CancellationToken
  ): Promise<ProgressComputeResponse> {
    if (this.isShutdown) {
      throw new Error('Worker is shutdown')
    }

    const request: ProgressComputeRequest = { samples, targetHz }
    return this.sendMessage('COMPUTE_PROGRESS', request, cancellationToken) as Promise<ProgressComputeResponse>
  }

  /**
   * Compute ETA based on recent progress samples
   */
  async computeETA(
    samples: Array<{ timestamp: number; progress: number }>,
    cancellationToken?: CancellationToken
  ): Promise<ProgressComputeResponse> {
    if (this.isShutdown) {
      throw new Error('Worker is shutdown')
    }

    return this.sendMessage('COMPUTE_ETA', samples, cancellationToken) as Promise<ProgressComputeResponse>
  }

  /**
   * Shutdown the worker and clean up resources
   */
  async shutdown(): Promise<void> {
    if (this.isShutdown) return

    this.isShutdown = true

    // Cancel all pending requests
    for (const [id, request] of Array.from(this.pendingRequests.entries())) {
      clearTimeout(request.timeout)
      request.reject(new Error('Worker is shutting down'))
    }
    this.pendingRequests.clear()

    // Send shutdown message and terminate
    try {
      await this.sendMessage('SHUTDOWN', {})
    } catch {
      // Ignore errors during shutdown
    }
    
    this.worker.terminate()
  }

  private async sendMessage(
    type: string, 
    data: unknown,
    cancellationToken?: CancellationToken,
    timeoutMs = 5000
  ): Promise<unknown> {
    if (this.isShutdown) {
      throw new Error('Worker is shutdown')
    }

    if (cancellationToken?.isCancelled) {
      throw new CancellationError()
    }

    const id = String(this.nextId++)
    const message: WorkerMessage = { type, id, data }

    return new Promise<unknown>((resolve, reject) => {
      // Set up timeout
      const timeout = window.setTimeout(() => {
        this.pendingRequests.delete(id)
        reject(new Error(`Worker request timed out after ${timeoutMs}ms`))
      }, timeoutMs)

      // Set up cancellation
      cancellationToken?.onCancelled(() => {
        const request = this.pendingRequests.get(id)
        if (request) {
          this.pendingRequests.delete(id)
          clearTimeout(request.timeout)
          reject(new CancellationError())
        }
      })

      // Store pending request
      this.pendingRequests.set(id, { resolve, reject, timeout })

      // Send message to worker
      try {
        this.worker.postMessage(message)
      } catch (error) {
        this.pendingRequests.delete(id)
        clearTimeout(timeout)
        reject(error)
      }
    })
  }

  private handleMessage(event: MessageEvent<WorkerResponse>): void {
    const { id, result, error } = event.data
    const request = this.pendingRequests.get(id)
    
    if (!request) {
      console.warn('Received response for unknown request:', id)
      return
    }

    this.pendingRequests.delete(id)
    clearTimeout(request.timeout)

    if (error) {
      request.reject(new Error(error))
    } else {
      request.resolve(result)
    }
  }

  private handleError(error: ErrorEvent): void {
    console.error('Worker error:', error)
    
    // Reject all pending requests
    for (const [id, request] of Array.from(this.pendingRequests.entries())) {
      clearTimeout(request.timeout)
      request.reject(new Error(`Worker error: ${error.message}`))
    }
    this.pendingRequests.clear()
  }
}

/**
 * Create a worker channel for progress computations
 */
export function createProgressWorker(): WorkerChannel {
  // Create worker from the progress worker script
  const workerBlob = new Blob([
    // Import the worker script content - in a real implementation this would be
    // a separate file or bundled appropriately
    `
    // Inline worker implementation for demo purposes
    class ProgressSmoother {
      constructor() {
        this.samples = [];
        this.maxSamples = 50;
        this.minSamples = 3;
      }

      addSample(timestamp, progress) {
        this.samples.push({ timestamp, progress });
        if (this.samples.length > this.maxSamples) {
          this.samples.shift();
        }
      }

      computeSmoothedProgress(targetHz) {
        if (this.samples.length < this.minSamples) {
          const latest = this.samples[this.samples.length - 1];
          return {
            smoothedProgress: latest?.progress ?? 0,
            rate: 0
          };
        }

        const alpha = Math.min(1.0, targetHz / 60.0);
        let smoothed = this.samples[0].progress;
        
        for (let i = 1; i < this.samples.length; i++) {
          smoothed = alpha * this.samples[i].progress + (1 - alpha) * smoothed;
        }

        const rate = this.calculateRate();
        let eta;
        if (rate > 0 && smoothed < 1.0) {
          eta = (1.0 - smoothed) / rate;
        }

        return {
          smoothedProgress: Math.max(0, Math.min(1, smoothed)),
          rate,
          eta
        };
      }

      calculateRate() {
        if (this.samples.length < 2) return 0;

        const n = this.samples.length;
        let sumX = 0, sumY = 0, sumXY = 0, sumXX = 0;

        for (const sample of this.samples) {
          const x = sample.timestamp / 1000;
          const y = sample.progress;
          sumX += x;
          sumY += y;
          sumXY += x * y;
          sumXX += x * x;
        }

        const denominator = n * sumXX - sumX * sumX;
        if (Math.abs(denominator) < 1e-10) return 0;

        return (n * sumXY - sumX * sumY) / denominator;
      }

      reset() {
        this.samples.length = 0;
      }
    }

    const smoother = new ProgressSmoother();

    self.onmessage = (event) => {
      const { type, id, data } = event.data;
      
      try {
        let result;
        
        switch (type) {
          case 'INIT':
            smoother.reset();
            result = { initialized: true };
            break;
          case 'COMPUTE_PROGRESS':
            for (const sample of data.samples) {
              smoother.addSample(sample.timestamp, sample.progress);
            }
            result = smoother.computeSmoothedProgress(data.targetHz);
            break;
          case 'COMPUTE_ETA':
            if (data.length > 0) {
              const latest = data[data.length - 1];
              smoother.addSample(latest.timestamp, latest.progress);
            }
            result = smoother.computeSmoothedProgress(2);
            break;
          case 'SHUTDOWN':
            smoother.reset();
            result = { shutdown: true };
            break;
          default:
            throw new Error('Unknown message type: ' + type);
        }
        
        self.postMessage({ id, result });
      } catch (error) {
        self.postMessage({ id, error: error.message });
      }
    };
    `
  ], { type: 'application/javascript' })

  const workerUrl = URL.createObjectURL(workerBlob)
  
  return new WorkerChannel(workerUrl)
}

/**
 * Progress smoother that uses a Web Worker for heavy computations
 */
export class ProgressSmoother {
  private worker: WorkerChannel
  private samples: Array<{ timestamp: number; progress: number }> = []
  private isInitialized = false

  constructor() {
    this.worker = createProgressWorker()
  }

  async initialize(): Promise<void> {
    if (this.isInitialized) return
    
    await this.worker.initialize()
    this.isInitialized = true
  }

  async addSample(progress: number): Promise<ProgressComputeResponse> {
    if (!this.isInitialized) {
      await this.initialize()
    }

    const timestamp = Date.now()
    this.samples.push({ timestamp, progress })
    
    // Keep only recent samples
    if (this.samples.length > 20) {
      this.samples = this.samples.slice(-20)
    }

    return this.worker.computeProgress(this.samples, 5)
  }

  async shutdown(): Promise<void> {
    await this.worker.shutdown()
    this.isInitialized = false
  }
}