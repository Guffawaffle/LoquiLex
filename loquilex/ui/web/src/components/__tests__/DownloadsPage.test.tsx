/**
 * Tests for Downloads Manager Page
 */

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import DownloadsPage from '../DownloadsPage'

// Mock the downloads store
vi.mock('../../orchestration/examples/downloads-store-fixed', () => ({
  useDownloadsStore: vi.fn(() => ({
    jobs: {},
    concurrencyLimit: 3,
    setConcurrencyLimit: vi.fn(),
    clearCompleted: vi.fn(),
    startDownload: vi.fn(),
    updateProgress: vi.fn(),
    markCompleted: vi.fn(),
    markFailed: vi.fn(),
  }))
}))

// Mock fetch for API calls
global.fetch = vi.fn()

describe('DownloadsPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    ;(global.fetch as any).mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ limit_mbps: 0 })
    })
  })

  it('renders downloads manager header', () => {
    render(<DownloadsPage />)
    
    expect(screen.getByText('Downloads Manager')).toBeInTheDocument()
    expect(screen.getByText('Manage model downloads with queue controls, progress tracking, and bandwidth limits')).toBeInTheDocument()
  })

  it('shows empty state when no downloads', () => {
    render(<DownloadsPage />)
    
    expect(screen.getByText('No downloads yet')).toBeInTheDocument()
    expect(screen.getByText('Add a model download above to get started')).toBeInTheDocument()
    expect(screen.getByText('📦')).toBeInTheDocument()
  })

  it('displays correct statistics for empty queue', () => {
    render(<DownloadsPage />)
    
    // Check the statistics counters
    expect(screen.getByText('0').closest('div')?.textContent).toMatch(/0\s*Active/)
    expect(screen.getByText('0').closest('div')?.textContent).toMatch(/0\s*Queued/)
    expect(screen.getByText('0').closest('div')?.textContent).toMatch(/0\s*Completed/)
    expect(screen.getByText('0').closest('div')?.textContent).toMatch(/0\s*Total/)
  })

  it('has add download form with proper fields', () => {
    render(<DownloadsPage />)
    
    expect(screen.getByLabelText('Repository ID')).toBeInTheDocument()
    expect(screen.getByPlaceholderText('e.g., openai/whisper-tiny.en')).toBeInTheDocument()
    expect(screen.getByLabelText('Model Type')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Add Download' })).toBeInTheDocument()
  })

  it('has download controls section', () => {
    render(<DownloadsPage />)
    
    expect(screen.getByText('Queue Control')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Pause All/ })).toBeInTheDocument()
    expect(screen.getByText(/Max Concurrent Downloads: 3/)).toBeInTheDocument()
    expect(screen.getByText(/Bandwidth Limit: Unlimited/)).toBeInTheDocument()
  })

  it('enables add download button when repository ID is entered', async () => {
    render(<DownloadsPage />)
    
    const input = screen.getByPlaceholderText('e.g., openai/whisper-tiny.en')
    const button = screen.getByRole('button', { name: 'Add Download' })
    
    expect(button).toBeDisabled()
    
    fireEvent.change(input, { target: { value: 'openai/whisper-tiny' } })
    
    expect(button).not.toBeDisabled()
  })

  it('loads bandwidth limit on mount', async () => {
    render(<DownloadsPage />)
    
    await waitFor(() => {
      expect(global.fetch).toHaveBeenCalledWith('/models/downloads/bandwidth')
    })
  })

  it('calls pause/resume all API when button is clicked', async () => {
    ;(global.fetch as any).mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ paused_count: 0 })
    })

    render(<DownloadsPage />)
    
    const pauseButton = screen.getByRole('button', { name: /Pause All/ })
    fireEvent.click(pauseButton)
    
    await waitFor(() => {
      expect(global.fetch).toHaveBeenCalledWith('/models/downloads/pause-all', { method: 'POST' })
    })
  })

  it('updates bandwidth limit when slider changes', async () => {
    ;(global.fetch as any).mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ limit_mbps: 50, active: true })
    })

    render(<DownloadsPage />)
    
    // Wait for initial load
    await waitFor(() => {
      expect(global.fetch).toHaveBeenCalledWith('/models/downloads/bandwidth')
    })

    const slider = screen.getByRole('slider')
    fireEvent.change(slider, { target: { value: '50' } })
    
    await waitFor(() => {
      expect(global.fetch).toHaveBeenCalledWith('/models/downloads/bandwidth', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ limit_mbps: 50 })
      })
    })
  })
})