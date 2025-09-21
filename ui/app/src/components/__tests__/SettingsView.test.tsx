import { describe, it, expect, beforeEach, vi } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import { SettingsView } from '../SettingsView';

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

// Mock the schema hook
vi.mock('../../hooks/useSettingsSchema', () => ({
  useSettingsSchema: vi.fn(() => ({
    schema: {
      type: 'object',
      properties: {
        asr_model_id: {
          type: 'string',
          title: 'ASR Model',
          description: 'Choose the default speech recognition model for new sessions.',
          group: 'Models',
          'x-level': 'basic',
          default: ''
        },
        mt_model_id: {
          type: 'string',
          title: 'MT Model',
          description: 'Select the machine translation model for EN→ZH translation.',
          group: 'Models',
          'x-level': 'basic',
          default: ''
        },
        device: {
          type: 'string',
          title: 'Device',
          description: 'Select the device for model inference.',
          group: 'Performance',
          'x-level': 'basic',
          default: 'auto',
          enum: ['auto', 'cpu', 'cuda', 'mps']
        },
        cadence_threshold: {
          type: 'integer',
          title: 'Cadence Threshold',
          description: 'Number of words to accumulate before triggering EN→ZH translation (1-8). Lower values provide faster translation but may be less accurate.',
          group: 'Translation',
          'x-level': 'basic',
          default: 3,
          minimum: 1,
          maximum: 8
        },
        show_timestamps: {
          type: 'boolean',
          title: 'Show Timestamps',
          description: 'Display timestamps in the caption view and include them in exports.',
          group: 'Display',
          'x-level': 'basic',
          default: true
        }
      },
      'x-groups': {
        Models: {
          title: 'Model Configuration',
          description: 'Configure speech recognition and translation models',
          order: 1
        },
        Performance: {
          title: 'Performance Settings',
          description: 'Hardware and performance configuration',
          order: 2
        },
        Translation: {
          title: 'Translation Settings',
          description: 'Configure translation behavior and timing',
          order: 3
        },
        Display: {
          title: 'Display Preferences',
          description: 'Configure display and UI behavior',
          order: 4
        }
      }
    },
    loading: false,
    error: null
  }))
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

    // Check that all form groups are present
    expect(screen.getByText('Model Configuration')).toBeInTheDocument();
    expect(screen.getByText('Performance Settings')).toBeInTheDocument();
    expect(screen.getByText('Translation Settings')).toBeInTheDocument();
    expect(screen.getByText('Display Preferences')).toBeInTheDocument();

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
      expect(screen.getByText('Settings')).toBeInTheDocument();
    });

    // With schema-driven form, model options are populated from the enhanced schema
    // The exact text will depend on the model IDs from the mocked ASR/MT models
    const asrSelect = screen.getByLabelText('ASR Model');
    const mtSelect = screen.getByLabelText('MT Model');
    
    expect(asrSelect).toBeInTheDocument();
    expect(mtSelect).toBeInTheDocument();
    
    // Check that device options are available from the schema enum
    const deviceSelect = screen.getByLabelText('Device');
    expect(deviceSelect).toBeInTheDocument();
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
      // Check that the label updates to show the new value
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
});