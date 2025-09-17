/**
 * Progress Worker - Offloads progress and ETA computations
 * 
 * This Web Worker handles progress smoothing and ETA calculations
 * off the main thread to prevent UI jank.
 * Now uses shared algorithm to eliminate code duplication.
 */

import type { 
  WorkerMessage, 
  WorkerResponse, 
  ProgressComputeRequest, 
  ProgressComputeResponse 
} from '../types'
// Import shared algorithm to eliminate code duplication
import { ProgressSmoothingAlgorithm } from './progress-worker-implementation'

// Global worker state using shared algorithm
const smoother = new ProgressSmoothingAlgorithm()

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