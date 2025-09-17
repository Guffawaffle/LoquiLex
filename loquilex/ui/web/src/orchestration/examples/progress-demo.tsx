/**
 * Progress Demo - Worker Channel Example
 * 
 * Demonstrates the Web Worker channel for progress smoothing
 * without main-thread jank.
 */

import React, { useState, useEffect, useRef } from 'react'
import { ProgressSmoother } from '../worker/worker-channel'

export function ProgressDemo() {
  const [progress, setProgress] = useState(0)
  const [smoothedProgress, setSmoothedProgress] = useState(0)
  const [rate, setRate] = useState(0)
  const [eta, setEta] = useState<number | undefined>()
  const [isRunning, setIsRunning] = useState(false)
  
  const smootherRef = useRef<ProgressSmoother | null>(null)
  const intervalRef = useRef<number | null>(null)

  useEffect(() => {
    // Initialize the progress smoother
    const initSmoother = async () => {
      const smoother = new ProgressSmoother()
      await smoother.initialize()
      smootherRef.current = smoother
    }
    
    initSmoother()

    return () => {
      // Cleanup
      if (smootherRef.current) {
        smootherRef.current.shutdown()
      }
      if (intervalRef.current) {
        clearInterval(intervalRef.current)
      }
    }
  }, [])

  const startSimulation = async () => {
    if (!smootherRef.current || isRunning) return
    
    setIsRunning(true)
    setProgress(0)
    setSmoothedProgress(0)
    
    // Simulate a download with variable progress
    intervalRef.current = window.setInterval(async () => {
      setProgress(prev => {
        const newProgress = Math.min(prev + Math.random() * 0.05, 1.0)
        
        // Send to worker for smoothing
        if (smootherRef.current) {
          smootherRef.current.addSample(newProgress).then(result => {
            setSmoothedProgress(result.smoothedProgress)
            setRate(result.rate)
            setEta(result.eta)
          })
        }
        
        if (newProgress >= 1.0) {
          setIsRunning(false)
          if (intervalRef.current) {
            clearInterval(intervalRef.current)
            intervalRef.current = null
          }
        }
        
        return newProgress
      })
    }, 50) // 20 Hz updates
  }

  const stopSimulation = () => {
    setIsRunning(false)
    if (intervalRef.current) {
      clearInterval(intervalRef.current)
      intervalRef.current = null
    }
  }

  const formatTime = (seconds: number | undefined): string => {
    if (!seconds || !isFinite(seconds)) return 'Unknown'
    const mins = Math.floor(seconds / 60)
    const secs = Math.floor(seconds % 60)
    return `${mins}:${secs.toString().padStart(2, '0')}`
  }

  const formatRate = (bytesPerSec: number): string => {
    if (bytesPerSec < 1000) return `${bytesPerSec.toFixed(1)} B/s`
    if (bytesPerSec < 1000000) return `${(bytesPerSec / 1000).toFixed(1)} KB/s`
    return `${(bytesPerSec / 1000000).toFixed(1)} MB/s`
  }

  return (
    <div className="p-6 max-w-2xl mx-auto">
      <h2 className="text-2xl font-bold mb-4">Progress Smoothing Demo</h2>
      <p className="text-gray-600 mb-6">
        This demo shows how the Web Worker channel smooths progress updates 
        at 2-10 Hz without causing main-thread jank.
      </p>
      
      <div className="space-y-4">
        {/* Controls */}
        <div className="flex gap-2">
          <button
            onClick={startSimulation}
            disabled={isRunning || !smootherRef.current}
            className="px-4 py-2 bg-blue-500 text-white rounded disabled:opacity-50"
          >
            Start Simulation
          </button>
          <button
            onClick={stopSimulation}
            disabled={!isRunning}
            className="px-4 py-2 bg-red-500 text-white rounded disabled:opacity-50"
          >
            Stop
          </button>
        </div>

        {/* Progress Bars */}
        <div className="space-y-3">
          <div>
            <label className="block text-sm font-medium mb-1">
              Raw Progress (jittery)
            </label>
            <div className="w-full bg-gray-200 rounded-full h-4">
              <div 
                className="bg-red-400 h-4 rounded-full transition-all duration-75"
                style={{ width: `${progress * 100}%` }}
              />
            </div>
            <span className="text-sm text-gray-600">{(progress * 100).toFixed(1)}%</span>
          </div>
          
          <div>
            <label className="block text-sm font-medium mb-1">
              Smoothed Progress (worker-computed)
            </label>
            <div className="w-full bg-gray-200 rounded-full h-4">
              <div 
                className="bg-green-500 h-4 rounded-full transition-all duration-300"
                style={{ width: `${smoothedProgress * 100}%` }}
              />
            </div>
            <span className="text-sm text-gray-600">{(smoothedProgress * 100).toFixed(1)}%</span>
          </div>
        </div>

        {/* Statistics */}
        <div className="grid grid-cols-2 gap-4 p-4 bg-gray-50 rounded">
          <div>
            <span className="block text-sm font-medium text-gray-700">Rate:</span>
            <span className="text-lg">{formatRate(rate * 1000000)}</span>
          </div>
          <div>
            <span className="block text-sm font-medium text-gray-700">ETA:</span>
            <span className="text-lg">{formatTime(eta)}</span>
          </div>
        </div>

        {/* Info */}
        <div className="p-4 bg-blue-50 rounded text-sm text-blue-800">
          <strong>How it works:</strong> The raw progress updates at 20 Hz with random jitter, 
          but the Web Worker smooths them to a steady 5 Hz rate using exponential moving averages 
          and linear regression for rate calculation. This prevents UI jank while providing 
          accurate progress feedback.
        </div>
      </div>
    </div>
  )
}