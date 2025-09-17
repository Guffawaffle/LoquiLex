/**
 * Progress Worker Implementation - Separate worker file
 * 
 * This is the extracted worker implementation that was previously inline.
 * It provides progress smoothing using exponential moving averages.
 */

// Shared progress smoothing algorithm - single source of truth
export class ProgressSmoothingAlgorithm {
  private samples: Array<{ timestamp: number; progress: number }> = []
  private readonly maxSamples = 50
  private readonly minSamples = 3

  addSample(timestamp: number, progress: number): void {
    this.samples.push({ timestamp, progress })
    if (this.samples.length > this.maxSamples) {
      this.samples.shift()
    }
  }

  computeSmoothedProgress(targetHz: number): {
    smoothedProgress: number
    rate: number
    eta?: number
  } {
    if (this.samples.length < this.minSamples) {
      const latest = this.samples[this.samples.length - 1]
      return {
        smoothedProgress: latest?.progress ?? 0,
        rate: 0
      }
    }

    // Exponential moving average calculation - unified implementation
    const alpha = Math.min(1.0, targetHz / 60.0)
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

// Worker implementation using the shared algorithm
const smoother = new ProgressSmoothingAlgorithm()

self.onmessage = (event) => {
  const { type, id, data } = event.data
  
  try {
    let result: unknown
    
    switch (type) {
      case 'INIT':
        smoother.reset()
        result = { initialized: true }
        break
      case 'COMPUTE_PROGRESS':
        for (const sample of data.samples) {
          smoother.addSample(sample.timestamp, sample.progress)
        }
        result = smoother.computeSmoothedProgress(data.targetHz)
        break
      case 'COMPUTE_ETA':
        if (data.length > 0) {
          const latest = data[data.length - 1]
          smoother.addSample(latest.timestamp, latest.progress)
        }
        result = smoother.computeSmoothedProgress(2)
        break
      case 'SHUTDOWN':
        smoother.reset()
        result = { shutdown: true }
        break
      default:
        throw new Error('Unknown message type: ' + type)
    }
    
    self.postMessage({ id, result })
  } catch (error) {
    self.postMessage({ id, error: error.message })
  }
}