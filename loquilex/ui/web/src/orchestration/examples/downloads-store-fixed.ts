/**
 * Example Downloads Store - Demonstrates orchestration patterns
 * 
 * This example shows how to build a downloads orchestrator using
 * the orchestration layer utilities and patterns.
 */

import { create } from 'zustand'
import type { 
  AsyncOperation,
  DownloadProgressData,
  DownloadCompletedData,
  DownloadFailedData,
  CancellationToken
} from '../types'
import {
  createAsyncOperation,
  createPendingOperation,
  createSuccessOperation,
  createErrorOperation,
  createCancelledOperation,
  isLoading
} from '../store/helpers'
import { 
  createConcurrencyLimiter,
  createCancellationToken,
  withRetry
} from '../index'

// ===== Types =====

export interface DownloadJob {
  id: string
  repoId: string
  type: 'asr' | 'mt'
  operation: AsyncOperation<DownloadResult>
  progress: number
  eta?: number
  rate?: number
  cancellationToken?: CancellationToken
  createdAt: number
  startedAt?: number
  completedAt?: number
}

export interface DownloadResult {
  localPath: string
  sizeBytes?: number
  durationSec?: number
}

export interface DownloadRequest {
  repoId: string
  type: 'asr' | 'mt'
}

export interface DownloadsState {
  jobs: Record<string, DownloadJob>
  concurrencyLimit: number
  maxRetries: number
}

export interface DownloadsActions {
  startDownload: (request: DownloadRequest) => Promise<string>
  cancelDownload: (jobId: string) => void
  pauseDownload: (jobId: string) => void
  resumeDownload: (jobId: string) => void
  clearCompleted: () => void
  updateProgress: (jobId: string, data: DownloadProgressData) => void
  markCompleted: (jobId: string, data: DownloadCompletedData) => void
  markFailed: (jobId: string, data: DownloadFailedData) => void
  setConcurrencyLimit: (limit: number) => void
}

export type DownloadsStore = DownloadsState & DownloadsActions

// ===== Store Implementation =====

// Global concurrency limiter for downloads
const concurrencyLimiter = createConcurrencyLimiter({ 
  maxConcurrent: 3, 
  queueLimit: 10 
})

// Mock API function (in real implementation, this would call the actual API)
async function apiStartDownload(request: DownloadRequest): Promise<{ job_id: string }> {
  // Simulate API call delay
  await new Promise(resolve => setTimeout(resolve, 100))
  // Fixed: Replace deprecated substr() with slice()
  return { job_id: `job_${Date.now()}_${Math.random().toString(36).slice(2, 11)}` }
}

export const useDownloadsStore = create<DownloadsStore>((set, get) => ({
  // ===== State =====
  jobs: {},
  concurrencyLimit: 3,
  maxRetries: 3,

  // ===== Actions =====
  
  async startDownload(request: DownloadRequest): Promise<string> {
    // Fixed: Replace deprecated substr() with slice()
    const jobId = `job_${Date.now()}_${Math.random().toString(36).slice(2, 11)}`
    const cancellationToken = createCancellationToken()
    
    // Create initial job
    const job: DownloadJob = {
      id: jobId,
      repoId: request.repoId,
      type: request.type,
      operation: createPendingOperation(),
      progress: 0,
      cancellationToken,
      createdAt: Date.now()
    }
    
    // Add job to state
    set(state => ({
      jobs: { ...state.jobs, [jobId]: job }
    }))
    
    // Execute download with concurrency limiting and retry logic
    concurrencyLimiter.execute(
      async () => {
        return withRetry(
          async () => {
            const response = await apiStartDownload(request)
            
            // Update job as started
            set(state => ({
              jobs: {
                ...state.jobs,
                [jobId]: {
                  ...state.jobs[jobId]!,
                  startedAt: Date.now()
                }
              }
            }))
            
            return response
          },
          { maxAttempts: get().maxRetries },
          cancellationToken
        )
      },
      cancellationToken
    ).catch(error => {
      // Handle failure
      set(state => ({
        jobs: {
          ...state.jobs,
          [jobId]: {
            ...state.jobs[jobId]!,
            operation: createErrorOperation(error)
          }
        }
      }))
    })
    
    return jobId
  },

  cancelDownload(jobId: string) {
    const job = get().jobs[jobId]
    if (!job) return
    
    // Cancel the operation
    job.cancellationToken?.cancel()
    
    // Update state
    set(state => ({
      jobs: {
        ...state.jobs,
        [jobId]: {
          ...job,
          operation: createCancelledOperation(job.operation.startTime)
        }
      }
    }))
  },

  pauseDownload(jobId: string) {
    // In a real implementation, this would pause the actual download
    console.log(`Pausing download ${jobId}`)
  },

  resumeDownload(jobId: string) {
    // In a real implementation, this would resume the actual download
    console.log(`Resuming download ${jobId}`)
  },

  clearCompleted() {
    set(state => {
      const jobs = { ...state.jobs }
      for (const [id, job] of Object.entries(jobs)) {
        if (job.operation.state === 'success' || job.operation.state === 'error') {
          delete jobs[id]
        }
      }
      return { jobs }
    })
  },

  updateProgress(jobId: string, data: DownloadProgressData) {
    set(state => {
      const job = state.jobs[jobId]
      if (!job) return state
      
      return {
        jobs: {
          ...state.jobs,
          [jobId]: {
            ...job,
            progress: data.pct / 100,
            rate: data.rate_bps,
            eta: data.eta_sec
          }
        }
      }
    })
  },

  markCompleted(jobId: string, data: DownloadCompletedData) {
    set(state => {
      const job = state.jobs[jobId]
      if (!job) return state
      
      const result: DownloadResult = {
        localPath: data.local_path,
        sizeBytes: data.size_bytes,
        durationSec: data.duration_sec
      }
      
      return {
        jobs: {
          ...state.jobs,
          [jobId]: {
            ...job,
            operation: createSuccessOperation(result, job.operation.startTime),
            progress: 1,
            completedAt: Date.now()
          }
        }
      }
    })
  },

  markFailed(jobId: string, data: DownloadFailedData) {
    set(state => {
      const job = state.jobs[jobId]
      if (!job) return state
      
      const error = new Error(`Download failed: ${data.error}`)
      
      return {
        jobs: {
          ...state.jobs,
          [jobId]: {
            ...job,
            operation: createErrorOperation(error, job.operation.startTime),
            completedAt: Date.now()
          }
        }
      }
    })
  },

  setConcurrencyLimit(limit: number) {
    set({ concurrencyLimit: limit })
    // Note: In a real implementation, you'd update the actual limiter
  }
}))

// ===== Selectors =====

export const downloadsSelectors = {
  // Get all jobs as array
  getAllJobs: (state: DownloadsState) => Object.values(state.jobs),
  
  // Get active (running) jobs
  getActiveJobs: (state: DownloadsState) => 
    Object.values(state.jobs).filter(job => isLoading(job.operation)),
  
  // Get completed jobs
  getCompletedJobs: (state: DownloadsState) =>
    Object.values(state.jobs).filter(job => job.operation.state === 'success'),
  
  // Get failed jobs
  getFailedJobs: (state: DownloadsState) =>
    Object.values(state.jobs).filter(job => job.operation.state === 'error'),
  
  // Get overall progress (for multiple downloads)
  getOverallProgress: (state: DownloadsState) => {
    const jobs = Object.values(state.jobs)
    if (jobs.length === 0) return 0
    
    const totalProgress = jobs.reduce((sum, job) => sum + job.progress, 0)
    return totalProgress / jobs.length
  },
  
  // Get job by ID
  getJob: (state: DownloadsState, jobId: string) => state.jobs[jobId],
  
  // Check if any downloads are active
  hasActiveDownloads: (state: DownloadsState) =>
    Object.values(state.jobs).some(job => isLoading(job.operation))
}