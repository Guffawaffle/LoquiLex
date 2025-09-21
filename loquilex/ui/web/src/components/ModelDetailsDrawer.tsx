import React, { useState, useEffect } from 'react'
import { api } from '../api'
import { RemoteModel } from '../types'

type Props = {
  modelId?: string
  model?: RemoteModel
  isOpen: boolean
  onClose: () => void
  onSelect?: (model: RemoteModel) => void
  onDownload?: (model: RemoteModel) => void
}

export default function ModelDetailsDrawer({ 
  modelId, 
  model: initialModel, 
  isOpen, 
  onClose, 
  onSelect, 
  onDownload 
}: Props) {
  const [model, setModel] = useState<RemoteModel | null>(initialModel || null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string>('')

  // Load model details if only ID is provided
  useEffect(() => {
    if (isOpen && modelId && !initialModel) {
      loadModelDetails(modelId)
    } else if (initialModel) {
      setModel(initialModel)
    }
  }, [isOpen, modelId, initialModel])

  const loadModelDetails = async (id: string) => {
    setLoading(true)
    setError('')
    
    try {
      const modelData = await api.search.model(id)
      setModel(modelData)
    } catch (err: any) {
      setError(`Failed to load model details: ${err.message || 'Unknown error'}`)
    } finally {
      setLoading(false)
    }
  }

  const formatSize = (bytes?: number) => {
    if (!bytes) return 'Unknown'
    const sizes = ['B', 'KB', 'MB', 'GB']
    const i = Math.floor(Math.log(bytes) / Math.log(1024))
    return `${(bytes / Math.pow(1024, i)).toFixed(1)} ${sizes[i]}`
  }

  const formatDate = (dateStr?: string) => {
    if (!dateStr) return 'Unknown'
    return new Date(dateStr).toLocaleDateString()
  }

  const getTaskColor = (task: string) => {
    switch (task) {
      case 'asr': return 'bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200'
      case 'mt': return 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200'
      case 'tts': return 'bg-purple-100 text-purple-800 dark:bg-purple-900 dark:text-purple-200'
      default: return 'bg-gray-100 text-gray-800 dark:bg-gray-900 dark:text-gray-200'
    }
  }

  const getProviderColor = (provider: string) => {
    switch (provider) {
      case 'huggingface': return 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-200'
      case 'openai': return 'bg-emerald-100 text-emerald-800 dark:bg-emerald-900 dark:text-emerald-200'
      case 'local': return 'bg-slate-100 text-slate-800 dark:bg-slate-800 dark:text-slate-200'
      default: return 'bg-gray-100 text-gray-800 dark:bg-gray-900 dark:text-gray-200'
    }
  }

  if (!isOpen) return null

  return (
    <div className="fixed inset-0 z-50 overflow-hidden">
      {/* Backdrop */}
      <div 
        className="absolute inset-0 bg-black bg-opacity-50"
        onClick={onClose}
      />
      
      {/* Drawer */}
      <div className="absolute right-0 top-0 h-full w-full max-w-2xl bg-white dark:bg-slate-900 shadow-xl overflow-y-auto">
        {/* Header */}
        <div className="sticky top-0 bg-white dark:bg-slate-900 border-b border-slate-200 dark:border-slate-700 p-4 flex items-center justify-between">
          <h2 className="text-xl font-semibold">Model Details</h2>
          <button
            onClick={onClose}
            className="p-2 hover:bg-slate-100 dark:hover:bg-slate-800 rounded-md"
          >
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        {/* Content */}
        <div className="p-6 space-y-6">
          {loading && (
            <div className="text-center py-8">
              <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600 mx-auto"></div>
              <p className="mt-2 text-slate-600 dark:text-slate-400">Loading model details...</p>
            </div>
          )}

          {error && (
            <div className="p-4 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-md">
              <p className="text-red-700 dark:text-red-300">{error}</p>
            </div>
          )}

          {model && !loading && (
            <>
              {/* Basic Info */}
              <div className="space-y-4">
                <div className="flex items-start justify-between">
                  <div className="flex-1 min-w-0">
                    <h1 className="text-2xl font-bold mb-2">{model.name}</h1>
                    <p className="text-slate-600 dark:text-slate-400 text-sm mb-3">
                      Model ID: <code className="bg-slate-100 dark:bg-slate-800 px-1 rounded text-xs">{model.id}</code>
                    </p>
                  </div>
                </div>

                {/* Tags */}
                <div className="flex flex-wrap gap-2">
                  <span className={`px-2 py-1 text-xs rounded-full ${getTaskColor(model.task)}`}>
                    {model.task.toUpperCase()}
                  </span>
                  <span className={`px-2 py-1 text-xs rounded-full ${getProviderColor(model.provider)}`}>
                    {model.provider}
                  </span>
                  {model.tags?.map((tag) => (
                    <span 
                      key={tag}
                      className="px-2 py-1 text-xs bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-300 rounded-full"
                    >
                      {tag}
                    </span>
                  ))}
                </div>

                {/* Description */}
                {model.description && (
                  <div>
                    <h3 className="font-semibold mb-2">Description</h3>
                    <p className="text-slate-600 dark:text-slate-400 leading-relaxed">
                      {model.description}
                    </p>
                  </div>
                )}
              </div>

              {/* Specifications */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4 p-4 bg-slate-50 dark:bg-slate-800 rounded-lg">
                <div>
                  <dt className="text-sm font-medium text-slate-500 dark:text-slate-400">Model Size</dt>
                  <dd className="text-lg font-semibold">{formatSize(model.size_bytes)}</dd>
                </div>

                {model.downloads && (
                  <div>
                    <dt className="text-sm font-medium text-slate-500 dark:text-slate-400">Downloads</dt>
                    <dd className="text-lg font-semibold">{model.downloads.toLocaleString()}</dd>
                  </div>
                )}

                {model.language && (
                  <div>
                    <dt className="text-sm font-medium text-slate-500 dark:text-slate-400">Primary Language</dt>
                    <dd className="text-lg font-semibold">{model.language}</dd>
                  </div>
                )}

                {model.updated_at && (
                  <div>
                    <dt className="text-sm font-medium text-slate-500 dark:text-slate-400">Last Updated</dt>
                    <dd className="text-lg font-semibold">{formatDate(model.updated_at)}</dd>
                  </div>
                )}

                {model.license && (
                  <div>
                    <dt className="text-sm font-medium text-slate-500 dark:text-slate-400">License</dt>
                    <dd className="text-lg font-semibold">{model.license}</dd>
                  </div>
                )}

                {model.model_class && (
                  <div>
                    <dt className="text-sm font-medium text-slate-500 dark:text-slate-400">Model Class</dt>
                    <dd className="text-lg font-semibold">{model.model_class}</dd>
                  </div>
                )}
              </div>

              {/* Languages */}
              {model.languages && model.languages.length > 0 && (
                <div>
                  <h3 className="font-semibold mb-2">Supported Languages</h3>
                  <div className="flex flex-wrap gap-2">
                    {model.languages.map((lang) => (
                      <span 
                        key={lang}
                        className="px-2 py-1 text-sm bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200 rounded"
                      >
                        {lang}
                      </span>
                    ))}
                  </div>
                </div>
              )}

              {/* Repository Link */}
              {model.repo_url && (
                <div>
                  <h3 className="font-semibold mb-2">Repository</h3>
                  <a
                    href={model.repo_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex items-center gap-2 text-blue-600 dark:text-blue-400 hover:underline"
                  >
                    {model.repo_url}
                    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
                    </svg>
                  </a>
                </div>
              )}

              {/* Actions */}
              <div className="flex gap-3 pt-4 border-t border-slate-200 dark:border-slate-700">
                <button
                  onClick={() => onSelect?.(model)}
                  className="flex-1 px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 font-medium"
                >
                  Select Model
                </button>
                <button
                  onClick={() => onDownload?.(model)}
                  className="flex-1 px-4 py-2 border border-slate-300 dark:border-slate-600 rounded-md hover:bg-slate-50 dark:hover:bg-slate-800 font-medium"
                >
                  Download
                </button>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  )
}