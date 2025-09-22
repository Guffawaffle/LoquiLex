import React, { useEffect, useState } from 'react'
import { api } from '../api'
import { HardwareSnapshot } from '../types'

type Props = {
  onRefresh?: () => void
}

const StatusBadge: React.FC<{ status: string; score: number }> = ({ status, score }) => {
  const colors = {
    excellent: 'bg-green-100 text-green-800 border-green-200',
    good: 'bg-blue-100 text-blue-800 border-blue-200', 
    fair: 'bg-yellow-100 text-yellow-800 border-yellow-200',
    poor: 'bg-orange-100 text-orange-800 border-orange-200',
    unusable: 'bg-red-100 text-red-800 border-red-200'
  }
  
  return (
    <span className={`px-2 py-1 rounded-md text-sm font-medium border ${colors[status as keyof typeof colors] || colors.poor}`}>
      {status.toUpperCase()} ({score}/100)
    </span>
  )
}

const WarningList: React.FC<{ warnings: string[] }> = ({ warnings }) => {
  if (warnings.length === 0) return null
  
  return (
    <div className="mt-2">
      <div className="text-sm font-medium text-orange-700 mb-1">⚠️ Warnings</div>
      <ul className="text-sm text-orange-600 space-y-1">
        {warnings.map((warning, i) => (
          <li key={i} className="flex items-start">
            <span className="text-orange-400 mr-1">•</span>
            <span>{warning}</span>
          </li>
        ))}
      </ul>
    </div>
  )
}

export default function HardwareInfo({ onRefresh }: Props) {
  const [snapshot, setSnapshot] = useState<HardwareSnapshot | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const fetchHardwareInfo = async () => {
    setLoading(true)
    setError(null)
    try {
      const data = await api.hardwareSnapshot()
      setSnapshot(data)
    } catch (e: any) {
      setError(e.detail?.error || e.message || 'Failed to get hardware info')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchHardwareInfo()
  }, [])

  const refresh = () => {
    fetchHardwareInfo()
    onRefresh?.()
  }

  if (loading) {
    return (
      <div className="bg-white dark:bg-slate-900 p-6 rounded-lg border border-slate-200 dark:border-slate-700">
        <div className="flex items-center gap-2 mb-4">
          <div className="text-lg font-semibold">Hardware Status</div>
          <div className="animate-spin w-4 h-4 border-2 border-slate-300 border-t-blue-600 rounded-full"></div>
        </div>
        <div className="text-slate-600 dark:text-slate-400">Detecting hardware...</div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="bg-white dark:bg-slate-900 p-6 rounded-lg border border-red-200 dark:border-red-800">
        <div className="flex items-center justify-between mb-4">
          <div className="text-lg font-semibold text-red-700 dark:text-red-400">Hardware Detection Failed</div>
          <button 
            onClick={refresh}
            className="px-3 py-1 text-sm bg-red-100 hover:bg-red-200 text-red-700 rounded-md transition-colors"
          >
            Retry
          </button>
        </div>
        <div className="text-red-600 dark:text-red-400">{error}</div>
      </div>
    )
  }

  if (!snapshot) return null

  return (
    <div className="bg-white dark:bg-slate-900 p-6 rounded-lg border border-slate-200 dark:border-slate-700">
      <div className="flex items-center justify-between mb-4">
        <div className="text-lg font-semibold">Hardware Status</div>
        <div className="flex items-center gap-2">
          <StatusBadge status={snapshot.overall_status} score={snapshot.overall_score} />
          <button 
            onClick={refresh}
            className="px-3 py-1 text-sm bg-slate-100 hover:bg-slate-200 dark:bg-slate-800 dark:hover:bg-slate-700 rounded-md transition-colors"
          >
            Refresh
          </button>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {/* CPU Info */}
        <div className="space-y-2">
          <div className="font-medium text-slate-900 dark:text-slate-100">CPU</div>
          <div className="text-sm space-y-1">
            <div className="truncate" title={snapshot.cpu.name}>
              <strong>Name:</strong> {snapshot.cpu.name}
            </div>
            <div>
              <strong>Cores:</strong> {snapshot.cpu.cores_logical} logical ({snapshot.cpu.cores_physical} physical)
            </div>
            {snapshot.cpu.frequency_mhz > 0 && (
              <div>
                <strong>Frequency:</strong> {snapshot.cpu.frequency_mhz.toFixed(0)} MHz
              </div>
            )}
            <div>
              <strong>Usage:</strong> {snapshot.cpu.usage_percent.toFixed(1)}%
            </div>
            <div className={`font-medium ${snapshot.cpu.meets_threshold ? 'text-green-600' : 'text-orange-600'}`}>
              {snapshot.cpu.meets_threshold ? '✓ Good' : '⚠️ Issues'}
            </div>
          </div>
          <WarningList warnings={snapshot.cpu.warnings} />
        </div>

        {/* GPU Info */}
        <div className="space-y-2">
          <div className="font-medium text-slate-900 dark:text-slate-100">GPU</div>
          {snapshot.gpus.map((gpu, i) => (
            <div key={i} className="text-sm space-y-1">
              <div className="truncate" title={gpu.name}>
                <strong>Name:</strong> {gpu.name}
              </div>
              {gpu.memory_total_mb > 0 && (
                <div>
                  <strong>Memory:</strong> {(gpu.memory_total_mb / 1024).toFixed(1)}GB 
                  ({(gpu.memory_free_mb / 1024).toFixed(1)}GB free)
                </div>
              )}
              <div>
                <strong>CUDA:</strong> {gpu.cuda_available ? 'Available' : 'Not available'}
              </div>
              <div className={`font-medium ${gpu.meets_threshold ? 'text-green-600' : 'text-orange-600'}`}>
                {gpu.meets_threshold ? '✓ Good' : '⚠️ Issues'}
              </div>
              <WarningList warnings={gpu.warnings} />
            </div>
          ))}
        </div>

        {/* Audio Devices */}
        <div className="space-y-2">
          <div className="font-medium text-slate-900 dark:text-slate-100">Audio Devices</div>
          {snapshot.audio_devices.slice(0, 3).map((device, i) => (
            <div key={i} className="text-sm space-y-1">
              <div className="truncate" title={device.name}>
                <strong>Name:</strong> {device.name}
                {device.is_default && <span className="ml-1 text-blue-600">(default)</span>}
              </div>
              <div>
                <strong>Channels:</strong> {device.channels}
              </div>
              <div>
                <strong>Sample Rate:</strong> {device.sample_rate} Hz
              </div>
              <div className={`font-medium ${device.is_available ? 'text-green-600' : 'text-orange-600'}`}>
                {device.is_available ? '✓ Available' : '⚠️ Not available'}
              </div>
              <WarningList warnings={device.warnings} />
            </div>
          ))}
          {snapshot.audio_devices.length > 3 && (
            <div className="text-sm text-slate-500">
              ... and {snapshot.audio_devices.length - 3} more devices
            </div>
          )}
        </div>
      </div>

      {/* Memory Info */}
      <div className="mt-4 pt-4 border-t border-slate-200 dark:border-slate-700">
        <div className="flex flex-wrap items-center gap-x-4 text-sm text-slate-600 dark:text-slate-400">
          <div>
            <strong>System Memory:</strong> {snapshot.memory_available_gb.toFixed(1)}GB available / {snapshot.memory_total_gb.toFixed(1)}GB total
          </div>
          <div>
            <strong>Platform:</strong> {snapshot.platform_info.system} {snapshot.platform_info.release}
          </div>
        </div>
      </div>

      {/* Overall Warnings */}
      {snapshot.warnings.length > 0 && (
        <div className="mt-4 pt-4 border-t border-slate-200 dark:border-slate-700">
          <WarningList warnings={snapshot.warnings} />
        </div>
      )}
    </div>
  )
}