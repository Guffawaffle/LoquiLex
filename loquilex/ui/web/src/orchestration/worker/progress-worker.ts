/**
 * Progress Worker - Offloads progress and ETA computations
 * 
 * This Web Worker handles progress smoothing and ETA calculations
 * off the main thread to prevent UI jank.
 */

import type { 
  WorkerMessage, 
  WorkerResponse, 
  ProgressComputeRequest, 
  ProgressComputeResponse 
} from '../types'

// Worker-side progress smoothing logic
class ProgressSmoother {
  private samples: Array<{ timestamp: number; progress: number }> = []
  private readonly maxSamples = 50
  private readonly minSamples = 3

  addSample(timestamp: number, progress: number): void {
    this.samples.push({ timestamp, progress })
    
    // Keep only recent samples
    if (this.samples.length > this.maxSamples) {
      this.samples.shift()
    }
  }

  computeSmoothedProgress(targetHz: number): ProgressComputeResponse {
    if (this.samples.length < this.minSamples) {
      const latest = this.samples[this.samples.length - 1]
      return {
        smoothedProgress: latest?.progress ?? 0,
        rate: 0,
        eta: undefined
      }
    }

    // Use exponential moving average for smoothing
    const alpha = Math.min(1.0, targetHz / 60.0) // Adapt to target frequency
    const firstSample = this.samples[0]
    if (!firstSample) {
      return { smoothedProgress: 0, rate: 0, eta: undefined }
    }
    
    let smoothed = firstSample.progress
    
    for (let i = 1; i < this.samples.length; i++) {
      const currentSample = this.samples[i]
      if (currentSample) {
        smoothed = alpha * currentSample.progress + (1 - alpha) * smoothed
      }
    }

    // Calculate rate (progress per second)
    const rate = this.calculateRate()

    // Calculate ETA if we have a positive rate
    let eta: number | undefined = undefined
    if (rate > 0 && smoothed < 1.0) {
      eta = (1.0 - smoothed) / rate
    }

    return {
      smoothedProgress: Math.max(0, Math.min(1, smoothed)),
      rate,
      eta
    }
  }

  private calculateRate(): number {
    if (this.samples.length < 2) return 0

    // Use linear regression for rate calculation
    const n = this.samples.length
    let sumX = 0, sumY = 0, sumXY = 0, sumXX = 0

    for (const sample of this.samples) {
      const x = sample.timestamp / 1000 // Convert to seconds
      const y = sample.progress
      
      sumX += x
      sumY += y
      sumXY += x * y
      sumXX += x * x
    }

    const denominator = n * sumXX - sumX * sumX
    if (Math.abs(denominator) < 1e-10) return 0

    return (n * sumXY - sumX * sumY) / denominator
  }

  reset(): void {
    this.samples.length = 0
  }
}

// Global worker state
const smoother = new ProgressSmoother()

// Handle messages from main thread
self.onmessage = (event: MessageEvent<WorkerMessage>) => {
  const { type, id, data } = event.data

  try {
    let result: unknown

    switch (type) {
      case 'INIT':
        smoother.reset()
        result = { initialized: true }
        break

      case 'COMPUTE_PROGRESS':
        const request = data as ProgressComputeRequest
        
        // Add all samples
        for (const sample of request.samples) {
          smoother.addSample(sample.timestamp, sample.progress)
        }
        
        result = smoother.computeSmoothedProgress(request.targetHz)
        break

      case 'COMPUTE_ETA':
        const samples = data as ProgressComputeRequest['samples']
        
        if (samples.length > 0) {
          const latest = samples[samples.length - 1]
          if (latest) {
            smoother.addSample(latest.timestamp, latest.progress)
          }
        }
        
        result = smoother.computeSmoothedProgress(2) // Low frequency for ETA
        break

      case 'SHUTDOWN':
        smoother.reset()
        result = { shutdown: true }
        break

      default:
        throw new Error(`Unknown message type: ${type}`)
    }

    // Send success response
    const response: WorkerResponse = { id, result }
    self.postMessage(response)

  } catch (error) {
    // Send error response
    const response: WorkerResponse = { 
      id, 
      error: error instanceof Error ? error.message : String(error) 
    }
    self.postMessage(response)
  }
}