/**
 * Downloads Manager Page - Queue UI with per-item progress, bandwidth caps, and controls
 */

import React, { useState, useEffect } from 'react'
import { useDownloadsStore } from '../orchestration/examples/downloads-store-fixed'
import type { DownloadJob } from '../orchestration/examples/downloads-store-fixed'
import type { DownloadMsg } from '../types'

// Component for individual download item with progress
function DownloadItem({ job }: { job: DownloadJob }) {
  const { cancelDownload, pauseDownload, resumeDownload } = useDownloadsStore()
  
  const progress = job.progress || 0
  const isActive = job.operation.state === 'loading'
  const isCompleted = job.operation.state === 'success'
  const isFailed = job.operation.state === 'error'
  const isCancelled = job.operation.state === 'cancelled'
  
  const getStatusText = () => {
    if (isCancelled) return 'Cancelled'
    if (isFailed) return 'Failed'
    if (isCompleted) return 'Completed'
    if (isActive) return 'Downloading...'
    return 'Queued'
  }
  
  const getStatusColor = () => {
    if (isCancelled) return 'text-gray-500'
    if (isFailed) return 'text-red-600'
    if (isCompleted) return 'text-green-600'
    if (isActive) return 'text-blue-600'
    return 'text-yellow-600'
  }

  return (
    <div className="border border-slate-200 dark:border-slate-700 rounded-lg p-4 space-y-3">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex-1">
          <h3 className="font-medium text-slate-900 dark:text-slate-100">
            {job.repoId}
          </h3>
          <p className="text-sm text-slate-600 dark:text-slate-400">
            {job.type.toUpperCase()} Model • {getStatusText()}
          </p>
        </div>
        <span className={`text-sm font-medium ${getStatusColor()}`}>
          {Math.round(progress)}%
        </span>
      </div>

      {/* Progress Bar */}
      <div className="w-full bg-slate-200 dark:bg-slate-700 rounded-full h-2">
        <div 
          className={`h-2 rounded-full transition-all duration-300 ${
            isCompleted ? 'bg-green-500' : 
            isFailed ? 'bg-red-500' : 
            isCancelled ? 'bg-gray-400' :
            'bg-blue-500'
          }`}
          style={{ width: `${Math.min(100, Math.max(0, progress))}%` }}
        />
      </div>

      {/* Details */}
      <div className="flex items-center justify-between text-xs text-slate-600 dark:text-slate-400">
        <div className="flex items-center space-x-4">
          {job.eta && isActive && (
            <span>ETA: {Math.round(job.eta)}s</span>
          )}
          {job.rate && isActive && (
            <span>Speed: {job.rate.toFixed(1)} MB/s</span>
          )}
          <span>Started: {new Date(job.createdAt).toLocaleTimeString()}</span>
        </div>
        
        {/* Action buttons */}
        <div className="flex items-center space-x-2">
          {isActive && (
            <>
              <button
                onClick={() => pauseDownload(job.id)}
                className="px-2 py-1 text-xs bg-yellow-100 text-yellow-700 rounded hover:bg-yellow-200"
              >
                Pause
              </button>
              <button
                onClick={() => cancelDownload(job.id)}
                className="px-2 py-1 text-xs bg-red-100 text-red-700 rounded hover:bg-red-200"
              >
                Cancel
              </button>
            </>
          )}
          {job.operation.state === 'pending' && (
            <>
              <button
                onClick={() => resumeDownload(job.id)}
                className="px-2 py-1 text-xs bg-green-100 text-green-700 rounded hover:bg-green-200"
              >
                Resume
              </button>
              <button
                onClick={() => cancelDownload(job.id)}
                className="px-2 py-1 text-xs bg-red-100 text-red-700 rounded hover:bg-red-200"
              >
                Cancel
              </button>
            </>
          )}
        </div>
      </div>
    </div>
  )
}

// Download controls component
function DownloadControls() {
  const { 
    jobs, 
    concurrencyLimit, 
    setConcurrencyLimit, 
    clearCompleted 
  } = useDownloadsStore()
  
  const [bandwidthLimit, setBandwidthLimit] = useState(0) // 0 = unlimited
  const [globalPaused, setGlobalPaused] = useState(false)

  // Load current bandwidth limit on component mount
  useEffect(() => {
    const loadBandwidthLimit = async () => {
      try {
        const response = await fetch('/models/downloads/bandwidth')
        if (response.ok) {
          const data = await response.json()
          setBandwidthLimit(data.limit_mbps)
        }
      } catch (error) {
        console.error('Failed to load bandwidth limit:', error)
      }
    }
    loadBandwidthLimit()
  }, [])

  const allJobs = Object.values(jobs)
  const activeJobs = allJobs.filter(job => job.operation.state === 'loading')
  const completedJobs = allJobs.filter(job => job.operation.state === 'success')
  const queuedJobs = allJobs.filter(job => job.operation.state === 'pending')

  const handlePauseResumeAll = async () => {
    try {
      const endpoint = globalPaused ? '/models/downloads/resume-all' : '/models/downloads/pause-all'
      const response = await fetch(endpoint, { method: 'POST' })
      
      if (response.ok) {
        setGlobalPaused(!globalPaused)
      } else {
        console.error('Failed to pause/resume downloads')
      }
    } catch (error) {
      console.error('Error toggling downloads:', error)
    }
  }

  const handleBandwidthChange = async (newLimit: number) => {
    setBandwidthLimit(newLimit)
    
    try {
      const response = await fetch('/models/downloads/bandwidth', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ limit_mbps: newLimit })
      })
      
      if (!response.ok) {
        console.error('Failed to set bandwidth limit')
      }
    } catch (error) {
      console.error('Error setting bandwidth limit:', error)
    }
  }

  return (
    <div className="bg-slate-50 dark:bg-slate-800 rounded-lg p-4 space-y-4">
      {/* Statistics */}
      <div className="grid grid-cols-4 gap-4 text-center">
        <div>
          <div className="text-2xl font-bold text-blue-600">{activeJobs.length}</div>
          <div className="text-xs text-slate-600 dark:text-slate-400">Active</div>
        </div>
        <div>
          <div className="text-2xl font-bold text-yellow-600">{queuedJobs.length}</div>
          <div className="text-xs text-slate-600 dark:text-slate-400">Queued</div>
        </div>
        <div>
          <div className="text-2xl font-bold text-green-600">{completedJobs.length}</div>
          <div className="text-xs text-slate-600 dark:text-slate-400">Completed</div>
        </div>
        <div>
          <div className="text-2xl font-bold text-slate-900 dark:text-slate-100">{allJobs.length}</div>
          <div className="text-xs text-slate-600 dark:text-slate-400">Total</div>
        </div>
      </div>

      <hr className="border-slate-200 dark:border-slate-700" />

      {/* Controls */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {/* Global Pause/Resume */}
        <div className="space-y-2">
          <label className="block text-sm font-medium text-slate-700 dark:text-slate-300">
            Queue Control
          </label>
          <button
            onClick={handlePauseResumeAll}
            className={`w-full px-4 py-2 rounded text-sm font-medium ${
              globalPaused 
                ? 'bg-green-600 text-white hover:bg-green-700' 
                : 'bg-yellow-600 text-white hover:bg-yellow-700'
            }`}
          >
            {globalPaused ? '▶️ Resume All' : '⏸️ Pause All'}
          </button>
        </div>

        {/* Concurrency Limit */}
        <div className="space-y-2">
          <label className="block text-sm font-medium text-slate-700 dark:text-slate-300">
            Max Concurrent Downloads: {concurrencyLimit}
          </label>
          <input
            type="range"
            min="1"
            max="10"
            value={concurrencyLimit}
            onChange={(e) => setConcurrencyLimit(parseInt(e.target.value))}
            className="w-full h-2 bg-slate-200 rounded-lg appearance-none cursor-pointer"
          />
        </div>

        {/* Bandwidth Limit */}
        <div className="space-y-2">
          <label className="block text-sm font-medium text-slate-700 dark:text-slate-300">
            Bandwidth Limit: {bandwidthLimit === 0 ? 'Unlimited' : `${bandwidthLimit} MB/s`}
          </label>
          <input
            type="range"
            min="0"
            max="100"
            step="5"
            value={bandwidthLimit}
            onChange={(e) => handleBandwidthChange(parseInt(e.target.value))}
            className="w-full h-2 bg-slate-200 rounded-lg appearance-none cursor-pointer"
          />
        </div>
      </div>

      {/* Action Buttons */}
      <div className="flex items-center justify-between">
        <button
          onClick={clearCompleted}
          disabled={completedJobs.length === 0}
          className="px-4 py-2 text-sm bg-slate-200 text-slate-700 rounded hover:bg-slate-300 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          Clear Completed ({completedJobs.length})
        </button>

        <div className="text-sm text-slate-600 dark:text-slate-400">
          Using {activeJobs.length}/{concurrencyLimit} slots
        </div>
      </div>
    </div>
  )
}

// Add New Download Form
function AddDownloadForm() {
  const { startDownload } = useDownloadsStore()
  const [repoId, setRepoId] = useState('')
  const [modelType, setModelType] = useState<'asr' | 'mt'>('asr')
  const [isSubmitting, setIsSubmitting] = useState(false)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!repoId.trim()) return

    setIsSubmitting(true)
    try {
      await startDownload({ repoId: repoId.trim(), type: modelType })
      setRepoId('')
    } catch (error) {
      console.error('Failed to start download:', error)
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <div className="bg-slate-50 dark:bg-slate-800 rounded-lg p-4">
      <h3 className="text-lg font-medium text-slate-900 dark:text-slate-100 mb-4">
        Add New Download
      </h3>
      
      <form onSubmit={handleSubmit} className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <div className="md:col-span-2">
          <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-1">
            Repository ID
          </label>
          <input
            type="text"
            value={repoId}
            onChange={(e) => setRepoId(e.target.value)}
            placeholder="e.g., openai/whisper-tiny.en"
            className="w-full px-3 py-2 border border-slate-300 rounded-md shadow-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
            disabled={isSubmitting}
          />
        </div>
        
        <div>
          <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-1">
            Model Type
          </label>
          <select
            value={modelType}
            onChange={(e) => setModelType(e.target.value as 'asr' | 'mt')}
            className="w-full px-3 py-2 border border-slate-300 rounded-md shadow-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
            disabled={isSubmitting}
          >
            <option value="asr">ASR (Speech-to-Text)</option>
            <option value="mt">MT (Translation)</option>
          </select>
        </div>
        
        <div className="flex items-end">
          <button
            type="submit"
            disabled={!repoId.trim() || isSubmitting}
            className="w-full px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {isSubmitting ? 'Adding...' : 'Add Download'}
          </button>
        </div>
      </form>
    </div>
  )
}

// Main Downloads Page Component
export default function DownloadsPage() {
  const { jobs, updateProgress, markCompleted, markFailed } = useDownloadsStore()
  const allJobs = Object.values(jobs)

  // WebSocket connection for download progress updates
  useEffect(() => {
    let ws: WebSocket | null = null
    
    const connectToDownloadUpdates = () => {
      const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
      const wsUrl = `${protocol}//${window.location.host}/ws/_download`
      
      try {
        ws = new WebSocket(wsUrl)
        
        ws.onopen = () => {
          console.log('Connected to download updates WebSocket')
        }
        
        ws.onmessage = (event) => {
          try {
            const message: DownloadMsg = JSON.parse(event.data)
            
            switch (message.type) {
              case 'download_progress':
                updateProgress(message.job_id, {
                  job_id: message.job_id,
                  repo_id: message.repo_id,
                  pct: message.pct
                })
                break
                
              case 'download_done':
                markCompleted(message.job_id, {
                  job_id: message.job_id,
                  local_path: message.local_path
                })
                break
                
              case 'download_error':
                markFailed(message.job_id, {
                  job_id: message.job_id,
                  error_code: 'DOWNLOAD_ERROR',
                  error_message: message.message
                })
                break
            }
          } catch (error) {
            console.error('Failed to parse download message:', error)
          }
        }
        
        ws.onclose = () => {
          console.log('Download updates WebSocket closed')
          // Reconnect after delay
          setTimeout(connectToDownloadUpdates, 3000)
        }
        
        ws.onerror = (error) => {
          console.error('Download updates WebSocket error:', error)
        }
      } catch (error) {
        console.error('Failed to connect to download updates:', error)
        setTimeout(connectToDownloadUpdates, 3000)
      }
    }
    
    connectToDownloadUpdates()
    
    return () => {
      if (ws) {
        ws.close()
      }
    }
  }, [updateProgress, markCompleted, markFailed])

  // Sort jobs: active first, then queued, then completed/failed
  const sortedJobs = allJobs.sort((a, b) => {
    const stateOrder = { loading: 0, pending: 1, success: 2, error: 3, cancelled: 4 }
    const aOrder = stateOrder[a.operation.state as keyof typeof stateOrder] ?? 5
    const bOrder = stateOrder[b.operation.state as keyof typeof stateOrder] ?? 5
    
    if (aOrder !== bOrder) return aOrder - bOrder
    return b.createdAt - a.createdAt // Newer first within same state
  })

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-slate-900 dark:text-slate-100">
          Downloads Manager
        </h1>
        <p className="text-slate-600 dark:text-slate-400">
          Manage model downloads with queue controls, progress tracking, and bandwidth limits
        </p>
      </div>

      {/* Controls */}
      <DownloadControls />

      {/* Add Download Form */}
      <AddDownloadForm />

      {/* Downloads List */}
      <div className="space-y-4">
        <h2 className="text-lg font-semibold text-slate-900 dark:text-slate-100">
          Download Queue ({allJobs.length})
        </h2>
        
        {sortedJobs.length === 0 ? (
          <div className="text-center py-12 text-slate-500 dark:text-slate-400">
            <div className="text-4xl mb-4">📦</div>
            <p className="text-lg mb-2">No downloads yet</p>
            <p className="text-sm">Add a model download above to get started</p>
          </div>
        ) : (
          <div className="space-y-3">
            {sortedJobs.map(job => (
              <DownloadItem key={job.id} job={job} />
            ))}
          </div>
        )}
      </div>
    </div>
  )
}