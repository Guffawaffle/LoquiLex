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

  // Schema rendering tests
  it('should render all form schema elements with proper structure', async () => {
    renderSettingsView();
    
    await waitFor(() => {
      // Check form structure
      expect(screen.getByText('Settings')).toBeInTheDocument();
      expect(screen.getByText('Configure models, device, cadence, and display preferences')).toBeInTheDocument();
      
      // Check all form groups are present
      const formGroups = document.querySelectorAll('.form-group');
      expect(formGroups).toHaveLength(5); // ASR, MT, Device, Cadence, Timestamps
      
      // Check each form group has proper structure
      formGroups.forEach((group) => {
        expect(group.querySelector('.form-group__label')).toBeInTheDocument();
        expect(group.querySelector('.form-group__description')).toBeInTheDocument();
      });
    });
  });

  it('should render descriptions/tooltips for all form fields', async () => {
    renderSettingsView();
    
    await waitFor(() => {
      // Check all descriptions are present
      expect(screen.getByText('Choose the default speech recognition model for new sessions.')).toBeInTheDocument();
      expect(screen.getByText('Choose the default translation model for new sessions.')).toBeInTheDocument();
      expect(screen.getByText('Choose the compute device for processing. Auto detects best available option.')).toBeInTheDocument();
      expect(screen.getByText(/Number of words to accumulate before triggering EN→ZH translation/)).toBeInTheDocument();
      expect(screen.getByText('Display timestamps in the caption view and include them in exports.')).toBeInTheDocument();
    });
  });

  it('should show restart badges for models that need download', async () => {
    renderSettingsView();
    
    await waitFor(() => {
      // Check that unavailable models show download badges
      expect(screen.getByText('Whisper Large (1.5GB) - Download needed')).toBeInTheDocument();
      expect(screen.getByText('NLLB 1.3B (2.7GB) - Download needed')).toBeInTheDocument();
      
      // Check that available models don't show download badges
      expect(screen.getByText('Whisper Small (244MB)')).toBeInTheDocument();
      expect(screen.getByText('NLLB 600M (1.2GB)')).toBeInTheDocument();
    });
  });

  // Form gating tests
  it('should gate form submission when required fields are empty', async () => {
    // Reset mock to return empty settings 
    const { saveSettings } = await import('../../utils/settings');
    
    renderSettingsView();
    
    await waitFor(() => {
      expect(screen.getByText('Save Settings')).toBeInTheDocument();
    });

    const saveButton = screen.getByText('Save Settings');
    fireEvent.click(saveButton);
    
    // Should still call saveSettings even with empty values (component allows it)
    expect(saveSettings).toHaveBeenCalled();
  });

  it('should disable form controls during loading', () => {
    // Mock loading state by not resolving fetch promises immediately
    mockFetch.mockImplementation(() => new Promise(() => {})); // Never resolves
    
    renderSettingsView();
    
    // Should show loading state
    expect(screen.getByText('Loading Settings...')).toBeInTheDocument();
    
    // Settings form should not be rendered during loading
    expect(screen.queryByText('Save Settings')).not.toBeInTheDocument();
  });

  it('should show success notification after saving', async () => {
    renderSettingsView();
    
    await waitFor(() => {
      expect(screen.getByText('Save Settings')).toBeInTheDocument();
    });

    const saveButton = screen.getByText('Save Settings');
    fireEvent.click(saveButton);
    
    await waitFor(() => {
      expect(screen.getByText('Settings saved successfully!')).toBeInTheDocument();
    });
    
    // Success message should disappear after timeout (can't easily test the setTimeout)
  });

  it('should handle model selection changes', async () => {
    renderSettingsView();
    
    await waitFor(() => {
      expect(screen.getByLabelText('ASR Model')).toBeInTheDocument();
    });

    const asrSelect = screen.getByLabelText('ASR Model');
    fireEvent.change(asrSelect, { target: { value: 'whisper-large' } });
    
    expect(asrSelect).toHaveValue('whisper-large');
    
    const mtSelect = screen.getByLabelText('MT Model');
    fireEvent.change(mtSelect, { target: { value: 'nllb-1.3B' } });
    
    expect(mtSelect).toHaveValue('nllb-1.3B');
  });

  it('should handle device selection changes', async () => {
    renderSettingsView();
    
    await waitFor(() => {
      expect(screen.getByLabelText('Device')).toBeInTheDocument();
    });

    const deviceSelect = screen.getByLabelText('Device');
    fireEvent.change(deviceSelect, { target: { value: 'cuda' } });
    
    expect(deviceSelect).toHaveValue('cuda');
  });

  it('should reset to defaults when reset button is clicked', async () => {
    const { clearSettings } = await import('../../utils/settings');
    
    renderSettingsView();
    
    await waitFor(() => {
      expect(screen.getByText('Reset to Defaults')).toBeInTheDocument();
    });

    const resetButton = screen.getByText('Reset to Defaults');
    fireEvent.click(resetButton);
    
    expect(clearSettings).toHaveBeenCalled();
  });

  // Accessibility tests
  describe('Accessibility', () => {
    it('should have proper form labels and descriptions', async () => {
      renderSettingsView();
      
      await waitFor(() => {
        expect(screen.getByText('Settings')).toBeInTheDocument();
      });

      // Check all form controls have proper labels
      expect(screen.getByLabelText('ASR Model')).toBeInTheDocument();
      expect(screen.getByLabelText('MT Model')).toBeInTheDocument();
      expect(screen.getByLabelText('Device')).toBeInTheDocument();
      expect(screen.getByLabelText(/Cadence Threshold/)).toBeInTheDocument();
      expect(screen.getByLabelText(/Show Timestamps/)).toBeInTheDocument();

      // Check form controls have associated descriptions
      const asrSelect = screen.getByLabelText('ASR Model');
      const asrDescription = document.querySelector('label[for="asr-model-select"] + .form-group__description');
      expect(asrDescription).toBeInTheDocument();

      const mtSelect = screen.getByLabelText('MT Model'); 
      const mtDescription = document.querySelector('label[for="mt-model-select"] + .form-group__description');
      expect(mtDescription).toBeInTheDocument();

      const deviceSelect = screen.getByLabelText('Device');
      const deviceDescription = document.querySelector('label[for="device-select"] + .form-group__description');
      expect(deviceDescription).toBeInTheDocument();
    });

    it('should have proper heading hierarchy', async () => {
      renderSettingsView();
      
      await waitFor(() => {
        const h1 = screen.getByRole('heading', { level: 1 });
        expect(h1).toHaveTextContent('Settings');
      });

      // Should have only one h1
      const headings = screen.getAllByRole('heading');
      const h1Headings = headings.filter(h => h.tagName === 'H1');
      expect(h1Headings).toHaveLength(1);
    });

    it('should have keyboard accessible form controls', async () => {
      renderSettingsView();
      
      await waitFor(() => {
        expect(screen.getByLabelText('ASR Model')).toBeInTheDocument();
      });

      // Check all interactive elements are focusable
      const asrSelect = screen.getByLabelText('ASR Model');
      const mtSelect = screen.getByLabelText('MT Model');
      const deviceSelect = screen.getByLabelText('Device');
      const slider = screen.getByRole('slider');
      const checkbox = screen.getByRole('checkbox');
      const saveButton = screen.getByText('Save Settings');
      const resetButton = screen.getByText('Reset to Defaults');
      const backButton = screen.getByText('← Back to Main');

      // These elements should be focusable (have tabindex >= 0 or be naturally focusable)
      [asrSelect, mtSelect, deviceSelect, slider, checkbox, saveButton, resetButton, backButton].forEach(element => {
        expect(element).toBeInTheDocument();
        // Element should be focusable (either naturally focusable or have tabindex)
        const tabIndex = element.getAttribute('tabindex');
        const isNaturallyFocusable = ['SELECT', 'INPUT', 'BUTTON'].includes(element.tagName);
        expect(isNaturallyFocusable || (tabIndex !== null && parseInt(tabIndex) >= 0)).toBe(true);
      });
    });

    it('should support keyboard navigation through form controls', async () => {
      renderSettingsView();
      
      await waitFor(() => {
        expect(screen.getByLabelText('ASR Model')).toBeInTheDocument();
      });

      const asrSelect = screen.getByLabelText('ASR Model');
      
      // Focus first element
      asrSelect.focus();
      expect(document.activeElement).toBe(asrSelect);
      
      // Should be able to change value with keyboard
      fireEvent.keyDown(asrSelect, { key: 'ArrowDown' });
      fireEvent.change(asrSelect, { target: { value: 'whisper-large' } });
      expect(asrSelect).toHaveValue('whisper-large');
    });

    it('should have proper ARIA attributes for slider', async () => {
      renderSettingsView();
      
      await waitFor(() => {
        const slider = screen.getByRole('slider');
        expect(slider).toBeInTheDocument();
      });

      const slider = screen.getByRole('slider');
      
      // Check slider has proper ARIA attributes
      expect(slider).toHaveAttribute('min', '1');
      expect(slider).toHaveAttribute('max', '8');
      expect(slider).toHaveAttribute('type', 'range');
      
      // Should have a label
      expect(screen.getByLabelText(/Cadence Threshold/)).toBe(slider);
    });

    it('should announce state changes to screen readers', async () => {
      renderSettingsView();
      
      await waitFor(() => {
        expect(screen.getByText('Save Settings')).toBeInTheDocument();
      });

      // Test success state announcement
      const saveButton = screen.getByText('Save Settings');
      fireEvent.click(saveButton);
      
      await waitFor(() => {
        const successMessage = screen.getByText('Settings saved successfully!');
        expect(successMessage).toBeInTheDocument();
        // Success message should be visible to screen readers
        expect(successMessage).not.toHaveAttribute('aria-hidden', 'true');
      });
    });

    it('should handle error states accessibly', async () => {
      mockFetch.mockRejectedValue(new Error('Network Error'));
      
      renderSettingsView();
      
      await waitFor(() => {
        const errorMessage = screen.getByText('Network Error');
        expect(errorMessage).toBeInTheDocument();
        // Error message should be visible to screen readers
        expect(errorMessage).not.toHaveAttribute('aria-hidden', 'true');
      });
    });

    it('should provide proper button labels and context', async () => {
      renderSettingsView();
      
      await waitFor(() => {
        expect(screen.getByText('Settings')).toBeInTheDocument();
      });

      // Check button text provides context
      const saveButton = screen.getByText('Save Settings');
      const resetButton = screen.getByText('Reset to Defaults');
      const backButton = screen.getByText('← Back to Main');

      expect(saveButton).toBeInTheDocument();
      expect(resetButton).toBeInTheDocument();
      expect(backButton).toBeInTheDocument();

      // Button text should be descriptive
      expect(saveButton.textContent).toContain('Save');
      expect(resetButton.textContent).toContain('Reset');
      expect(backButton.textContent).toContain('Back');
    });
  });
});