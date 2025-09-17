/**
 * Progress Worker - Handles progress smoothing and ETA calculations off the main thread
 * 
 * This Web Worker offloads progress computations to prevent UI jank during
 * intensive calculations. Supports configurable update frequencies (2-10 Hz).
 */

import type { 
  WorkerMessage, 
  WorkerResponse, 
  ProgressComputeRequest, 
  ProgressComputeResponse 
} from '../types'

/**
 * Progress smoothing algorithm with configurable frequency capping
 */
class ProgressSmoother {
  private samples: Array<{ timestamp: number; progress: number }> = []
  private readonly maxSamples = 50
  private readonly minSamples = 3

  addSample(timestamp: number, progress: number): void {
    this.samples.push({ timestamp, progress })
    if (this.samples.length > this.maxSamples) {
      this.samples.shift()
    }
  }

  computeSmoothedProgress(targetHz: number): ProgressComputeResponse {
    if (this.samples.length < this.minSamples) {
      const latest = this.samples[this.samples.length - 1]
      return {
        smoothedProgress: latest?.progress ?? 0,
        rate: 0
      }
    }

    // Clamp frequency to 2-10 Hz range for stability
    const cappedHz = Math.max(2, Math.min(10, targetHz))
    const alpha = Math.min(1.0, cappedHz / 60.0)
    let smoothed = this.samples[0].progress
    
    for (let i = 1; i < this.samples.length; i++) {
      smoothed = alpha * this.samples[i].progress + (1 - alpha) * smoothed
    }

    const rate = this.calculateRate()
    let eta: number | undefined
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

    const n = this.samples.length
    let sumX = 0, sumY = 0, sumXY = 0, sumXX = 0

    for (const sample of this.samples) {
      const x = sample.timestamp / 1000
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
        // Add all samples to the smoother
        for (const sample of request.samples) {
          smoother.addSample(sample.timestamp, sample.progress)
        }
        result = smoother.computeSmoothedProgress(request.targetHz)
        break
        
      case 'COMPUTE_ETA':
        const samples = data as ProgressComputeRequest['samples']
        if (samples.length > 0) {
          const latest = samples[samples.length - 1]
          smoother.addSample(latest.timestamp, latest.progress)
        }
        // Use low frequency for ETA calculations (more stable)
        result = smoother.computeSmoothedProgress(2)
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