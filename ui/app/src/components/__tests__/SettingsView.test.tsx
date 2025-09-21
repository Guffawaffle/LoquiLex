import { describe, it, expect, beforeEach, vi } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { BrowserRouter } from 'react-router-dom';
import { SettingsView } from '../SettingsView';

// Mock ResizeObserver for tooltips
global.ResizeObserver = vi.fn().mockImplementation(() => ({
  observe: vi.fn(),
  unobserve: vi.fn(),
  disconnect: vi.fn(),
}));

// Mock the settings module
vi.mock('../../utils/settings', () => ({
  loadSettings: vi.fn(() => ({
    asr_model_id: 'test-asr',
    mt_model_id: 'test-mt',
    device: 'auto',
    cadence_threshold: 3,
    show_timestamps: true,
  })),
  saveSettings: vi.fn(),
  clearSettings: vi.fn(),
  DEFAULT_SETTINGS: {
    asr_model_id: '',
    mt_model_id: '',
    device: 'auto',
    cadence_threshold: 3,
    show_timestamps: true,
  }
}));

// Mock fetch for model loading
const mockFetch = vi.fn();
(globalThis as any).fetch = mockFetch;

const mockAsrModels = [
  { id: 'whisper-small', name: 'Whisper Small', size: '244MB', available: true },
  { id: 'whisper-large', name: 'Whisper Large', size: '1.5GB', available: false },
];

const mockMtModels = [
  { id: 'nllb-600M', name: 'NLLB 600M', size: '1.2GB', available: true },
  { id: 'nllb-1.3B', name: 'NLLB 1.3B', size: '2.7GB', available: false },
];

function renderSettingsView() {
  return render(
    <BrowserRouter>
      <SettingsView />
    </BrowserRouter>
  );
}

describe('SettingsView', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockFetch.mockImplementation((url: string) => {
      if (url === '/models/asr') {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve(mockAsrModels),
        });
      }
      if (url === '/models/mt') {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve(mockMtModels),
        });
      }
      return Promise.resolve({ ok: false });
    });
  });

  it('should render settings form with all controls', async () => {
    renderSettingsView();
    
    // Wait for models to load
    await waitFor(() => {
      expect(screen.getByText('Settings')).toBeInTheDocument();
    });

    // Check that all form elements are present
    expect(screen.getByLabelText('ASR Model')).toBeInTheDocument();
    expect(screen.getByLabelText('MT Model')).toBeInTheDocument();
    expect(screen.getByLabelText('Device')).toBeInTheDocument();
    expect(screen.getByLabelText(/Cadence Threshold/)).toBeInTheDocument();
    expect(screen.getByLabelText(/Show Timestamps/)).toBeInTheDocument();
    
    // Check action buttons
    expect(screen.getByText('Save Settings')).toBeInTheDocument();
    expect(screen.getByText('Reset to Defaults')).toBeInTheDocument();
    expect(screen.getByText('← Back to Main')).toBeInTheDocument();
  });

  it('should load and display available models', async () => {
    renderSettingsView();
    
    await waitFor(() => {
      expect(screen.getByText('Whisper Small (244MB)')).toBeInTheDocument();
      expect(screen.getByText('Whisper Large (1.5GB) - Download needed')).toBeInTheDocument();
      expect(screen.getByText('NLLB 600M (1.2GB)')).toBeInTheDocument();
      expect(screen.getByText('NLLB 1.3B (2.7GB) - Download needed')).toBeInTheDocument();
    });
  });

  it('should update cadence threshold when slider changes', async () => {
    renderSettingsView();
    
    await waitFor(() => {
      const slider = screen.getByRole('slider');
      expect(slider).toBeInTheDocument();
    });

    const slider = screen.getByRole('slider');
    fireEvent.change(slider, { target: { value: '5' } });
    
    await waitFor(() => {
      expect(screen.getByText('Cadence Threshold: 5 words')).toBeInTheDocument();
    });
  });

  it('should toggle timestamps checkbox', async () => {
    renderSettingsView();
    
    await waitFor(() => {
      const checkbox = screen.getByRole('checkbox', { name: /Show Timestamps/ });
      expect(checkbox).toBeInTheDocument();
      expect(checkbox).toBeChecked(); // Should start checked based on mock
    });

    const checkbox = screen.getByRole('checkbox', { name: /Show Timestamps/ });
    fireEvent.click(checkbox);
    
    expect(checkbox).not.toBeChecked();
  });

  it('should show loading state initially', () => {
    renderSettingsView();
    
    expect(screen.getByText('Loading Settings...')).toBeInTheDocument();
  });

  it('should handle API errors gracefully', async () => {
    mockFetch.mockRejectedValue(new Error('API Error'));
    
    renderSettingsView();
    
    await waitFor(() => {
      expect(screen.getByText('API Error')).toBeInTheDocument();
    });
  });

  it('should validate cadence threshold is within range', async () => {
    renderSettingsView();
    
    await waitFor(() => {
      const slider = screen.getByRole('slider');
      expect(slider).toHaveAttribute('min', '1');
      expect(slider).toHaveAttribute('max', '8');
    });
  });

  it('should show tooltips on hover for accessibility', async () => {
    const user = userEvent.setup();
    renderSettingsView();
    
    await waitFor(() => {
      expect(screen.getByLabelText('ASR Model')).toBeInTheDocument();
    });

    // Test ASR Model tooltip
    const asrLabel = screen.getByLabelText('ASR Model');
    await user.hover(asrLabel);
    
    await waitFor(() => {
      expect(screen.getByRole('tooltip')).toBeInTheDocument();
      expect(screen.getByText(/speech recognition model/i)).toBeInTheDocument();
    });

    await user.unhover(asrLabel);
    
    await waitFor(() => {
      expect(screen.queryByRole('tooltip')).not.toBeInTheDocument();
    });
  });

  it('should show tooltips on focus for keyboard accessibility', async () => {
    const user = userEvent.setup();
    renderSettingsView();
    
    await waitFor(() => {
      expect(screen.getByDisplayValue('auto')).toBeInTheDocument();
    });

    // Test Device select tooltip on focus
    const deviceSelect = screen.getByDisplayValue('auto');
    await user.click(deviceSelect);
    
    await waitFor(() => {
      expect(screen.getByRole('tooltip')).toBeInTheDocument();
      expect(screen.getByText(/CUDA GPU provides/i)).toBeInTheDocument();
    });
  });

  it('should have proper ARIA attributes for tooltips', async () => {
    const user = userEvent.setup();
    renderSettingsView();
    
    await waitFor(() => {
      expect(screen.getByRole('button', { name: 'Save Settings' })).toBeInTheDocument();
    });

    const saveButton = screen.getByRole('button', { name: 'Save Settings' });
    await user.hover(saveButton);
    
    await waitFor(() => {
      const tooltip = screen.getByRole('tooltip');
      expect(tooltip).toHaveAttribute('role', 'tooltip');
      expect(tooltip).toHaveAttribute('aria-hidden', 'false');
      
      const tooltipId = tooltip.getAttribute('id');
      expect(saveButton).toHaveAttribute('aria-describedby', tooltipId);
    });
  });
});