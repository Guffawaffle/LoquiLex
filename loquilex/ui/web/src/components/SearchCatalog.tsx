import React, { useState, useEffect, useMemo } from 'react'
import { api } from '../api'
import { RemoteModel, SearchFilters, ModelTask, ModelProvider } from '../types'
import { RateLimiter } from '../orchestration/utils/throttle'

type Props = {
  onModelSelect?: (model: RemoteModel) => void
  onShowDetails?: (model: RemoteModel) => void
}

// Create rate limiter for search API calls (5 Hz max)
const searchRateLimiter = new RateLimiter(5)

export default function SearchCatalog({ onModelSelect, onShowDetails }: Props) {
  const [filters, setFilters] = useState<SearchFilters>({})
  const [models, setModels] = useState<RemoteModel[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string>('')
  const [page, setPage] = useState(1)
  const [hasNext, setHasNext] = useState(false)
  const [total, setTotal] = useState(0)
  const [debouncedQuery, setDebouncedQuery] = useState('')

  // Debounce search query
  useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedQuery(filters.query || '')
    }, 500)
    return () => clearTimeout(timer)
  }, [filters.query])

  // Search when filters or page changes
  useEffect(() => {
    searchModels()
  }, [debouncedQuery, filters.task, filters.language, filters.provider, filters.minSize, filters.maxSize, page])

  const searchModels = async () => {
    // Check rate limit before making request
    if (!searchRateLimiter.isAllowed()) {
      setError('Rate limit exceeded. Please wait before searching again.')
      return
    }

    setLoading(true)
    setError('')

    try {
      const searchFilters = { ...filters, query: debouncedQuery }
      const result = await api.search.models(searchFilters, page, 20)
      
      if (page === 1) {
        setModels(result.models)
      } else {
        setModels(prev => [...prev, ...result.models])
      }
      
      setHasNext(result.has_next)
      setTotal(result.total)
    } catch (err: any) {
      setError(`Search failed: ${err.message || 'Unknown error'}`)
    } finally {
      setLoading(false)
    }
  }

  const updateFilter = (key: keyof SearchFilters, value: any) => {
    setFilters(prev => ({ ...prev, [key]: value }))
    setPage(1) // Reset to first page when filter changes
  }

  const clearFilters = () => {
    setFilters({})
    setPage(1)
  }

  const loadMore = () => {
    if (hasNext && !loading) {
      setPage(prev => prev + 1)
    }
  }

  const formatSize = (bytes?: number) => {
    if (!bytes) return 'Unknown'
    const sizes = ['B', 'KB', 'MB', 'GB']
    const i = Math.floor(Math.log(bytes) / Math.log(1024))
    return `${(bytes / Math.pow(1024, i)).toFixed(1)} ${sizes[i]}`
  }

  return (
    <div className="max-w-6xl mx-auto p-4 space-y-6">
      {/* Search Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold">Search Model Catalog</h2>
          <p className="text-slate-600 dark:text-slate-400">
            {total > 0 ? `${total} models found` : 'Search across providers for AI models'}
          </p>
        </div>
        <button 
          onClick={clearFilters}
          className="px-3 py-2 text-sm border rounded-md hover:bg-slate-50 dark:hover:bg-slate-800"
        >
          Clear Filters
        </button>
      </div>

      {/* Search Filters */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 p-4 bg-slate-50 dark:bg-slate-900 rounded-lg">
        {/* Search Query */}
        <div className="lg:col-span-2">
          <label className="block text-sm font-medium mb-1">Search</label>
          <input
            type="text"
            placeholder="Model name or description..."
            className="w-full px-3 py-2 border rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            value={filters.query || ''}
            onChange={(e) => updateFilter('query', e.target.value)}
          />
        </div>

        {/* Task Filter */}
        <div>
          <label className="block text-sm font-medium mb-1">Task</label>
          <select
            className="w-full px-3 py-2 border rounded-md focus:ring-2 focus:ring-blue-500"
            value={filters.task || ''}
            onChange={(e) => updateFilter('task', e.target.value as ModelTask || undefined)}
          >
            <option value="">All Tasks</option>
            <option value="asr">Speech Recognition</option>
            <option value="mt">Translation</option>
            <option value="tts">Text-to-Speech</option>
            <option value="embedding">Embeddings</option>
          </select>
        </div>

        {/* Provider Filter */}
        <div>
          <label className="block text-sm font-medium mb-1">Provider</label>
          <select
            className="w-full px-3 py-2 border rounded-md focus:ring-2 focus:ring-blue-500"
            value={filters.provider || ''}
            onChange={(e) => updateFilter('provider', e.target.value as ModelProvider || undefined)}
          >
            <option value="">All Providers</option>
            <option value="huggingface">Hugging Face</option>
            <option value="openai">OpenAI</option>
            <option value="local">Local</option>
          </select>
        </div>

        {/* Language Filter */}
        <div>
          <label className="block text-sm font-medium mb-1">Language</label>
          <select
            className="w-full px-3 py-2 border rounded-md focus:ring-2 focus:ring-blue-500"
            value={filters.language || ''}
            onChange={(e) => updateFilter('language', e.target.value || undefined)}
          >
            <option value="">All Languages</option>
            <option value="en">English</option>
            <option value="zh">Chinese</option>
            <option value="es">Spanish</option>
            <option value="fr">French</option>
            <option value="de">German</option>
            <option value="ja">Japanese</option>
            <option value="ko">Korean</option>
          </select>
        </div>

        {/* Size Range */}
        <div>
          <label className="block text-sm font-medium mb-1">Min Size (MB)</label>
          <input
            type="number"
            placeholder="0"
            className="w-full px-3 py-2 border rounded-md focus:ring-2 focus:ring-blue-500"
            value={filters.minSize || ''}
            onChange={(e) => updateFilter('minSize', e.target.value ? parseInt(e.target.value) * 1024 * 1024 : undefined)}
          />
        </div>

        <div>
          <label className="block text-sm font-medium mb-1">Max Size (GB)</label>
          <input
            type="number"
            placeholder="10"
            className="w-full px-3 py-2 border rounded-md focus:ring-2 focus:ring-blue-500"
            value={filters.maxSize ? Math.round(filters.maxSize / (1024 * 1024 * 1024)) : ''}
            onChange={(e) => updateFilter('maxSize', e.target.value ? parseInt(e.target.value) * 1024 * 1024 * 1024 : undefined)}
          />
        </div>
      </div>

      {/* Error Display */}
      {error && (
        <div className="p-4 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-md">
          <p className="text-red-700 dark:text-red-300">{error}</p>
        </div>
      )}

      {/* Results */}
      <div className="space-y-4">
        {loading && models.length === 0 && (
          <div className="text-center py-8">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600 mx-auto"></div>
            <p className="mt-2 text-slate-600 dark:text-slate-400">Searching models...</p>
          </div>
        )}

        {models.length === 0 && !loading && (
          <div className="text-center py-12">
            <p className="text-slate-500 dark:text-slate-400">No models found. Try adjusting your filters.</p>
          </div>
        )}

        {models.map((model) => (
          <div
            key={model.id}
            className="p-4 border border-slate-200 dark:border-slate-700 rounded-lg hover:border-blue-300 dark:hover:border-blue-600 transition-colors"
          >
            <div className="flex items-start justify-between">
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 mb-2">
                  <h3 className="text-lg font-semibold truncate">{model.name}</h3>
                  <span className={`px-2 py-1 text-xs rounded-full ${
                    model.task === 'asr' ? 'bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200' :
                    model.task === 'mt' ? 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200' :
                    model.task === 'tts' ? 'bg-purple-100 text-purple-800 dark:bg-purple-900 dark:text-purple-200' :
                    'bg-gray-100 text-gray-800 dark:bg-gray-900 dark:text-gray-200'
                  }`}>
                    {model.task.toUpperCase()}
                  </span>
                  <span className="px-2 py-1 text-xs bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-300 rounded-full">
                    {model.provider}
                  </span>
                </div>
                
                {model.description && (
                  <p className="text-slate-600 dark:text-slate-400 text-sm mb-2 line-clamp-2">
                    {model.description}
                  </p>
                )}
                
                <div className="flex items-center gap-4 text-sm text-slate-500 dark:text-slate-400">
                  {model.size_bytes && (
                    <span>Size: {formatSize(model.size_bytes)}</span>
                  )}
                  {model.downloads && (
                    <span>Downloads: {model.downloads.toLocaleString()}</span>
                  )}
                  {model.language && (
                    <span>Language: {model.language}</span>
                  )}
                  {model.languages && model.languages.length > 0 && (
                    <span>Languages: {model.languages.slice(0, 3).join(', ')}{model.languages.length > 3 ? '...' : ''}</span>
                  )}
                </div>
              </div>
              
              <div className="flex items-center gap-2 ml-4">
                <button
                  onClick={() => onShowDetails?.(model)}
                  className="px-3 py-1 text-sm border border-slate-300 dark:border-slate-600 rounded-md hover:bg-slate-50 dark:hover:bg-slate-800"
                >
                  Details
                </button>
                <button
                  onClick={() => onModelSelect?.(model)}
                  className="px-3 py-1 text-sm bg-blue-600 text-white rounded-md hover:bg-blue-700"
                >
                  Select
                </button>
              </div>
            </div>
          </div>
        ))}

        {/* Load More */}
        {hasNext && (
          <div className="text-center py-4">
            <button
              onClick={loadMore}
              disabled={loading}
              className="px-6 py-2 border border-slate-300 dark:border-slate-600 rounded-md hover:bg-slate-50 dark:hover:bg-slate-800 disabled:opacity-50"
            >
              {loading ? 'Loading...' : 'Load More'}
            </button>
          </div>
        )}
      </div>
    </div>
  )
}