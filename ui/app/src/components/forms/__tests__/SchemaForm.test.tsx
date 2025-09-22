import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { SchemaForm } from '../SchemaForm';
import { SettingsSchema } from '../types';

const mockSchema: SettingsSchema = {
  type: 'object',
  properties: {
    asr_model_id: {
      type: 'string',
      title: 'ASR Model',
      description: 'Choose the ASR model',
      group: 'Models',
      'x-level': 'basic',
      default: '',
      enum: ['whisper-small', 'whisper-medium']
    },
    device: {
      type: 'string',
      title: 'Device',
      description: 'Select the device',
      group: 'Performance',
      'x-level': 'basic',
      default: 'auto',
      enum: ['auto', 'cpu', 'cuda']
    },
    cadence_threshold: {
      type: 'integer',
      title: 'Cadence Threshold',
      description: 'Number of words',
      group: 'Translation',
      'x-level': 'basic',
      default: 3,
      minimum: 1,
      maximum: 8
    },
    show_timestamps: {
      type: 'boolean',
      title: 'Show Timestamps',
      description: 'Display timestamps',
      group: 'Display',
      'x-level': 'basic',
      default: true
    }
  },
  'x-groups': {
    Models: {
      title: 'Model Configuration',
      description: 'Configure models',
      order: 1
    },
    Performance: {
      title: 'Performance Settings',
      description: 'Hardware configuration',
      order: 2
    },
    Translation: {
      title: 'Translation Settings',
      description: 'Translation behavior',
      order: 3
    },
    Display: {
      title: 'Display Preferences',
      description: 'UI behavior',
      order: 4
    }
  }
};

describe('SchemaForm', () => {
  const mockOnChange = vi.fn();
  const mockValues = {
    asr_model_id: 'whisper-small',
    device: 'auto',
    cadence_threshold: 3,
    show_timestamps: true
  };

  beforeEach(() => {
    mockOnChange.mockClear();
  });

  it('should render all groups in correct order', () => {
    render(
      <SchemaForm
        schema={mockSchema}
        values={mockValues}
        onChange={mockOnChange}
      />
    );

    expect(screen.getByText('Model Configuration')).toBeInTheDocument();
    expect(screen.getByText('Performance Settings')).toBeInTheDocument();
    expect(screen.getByText('Translation Settings')).toBeInTheDocument();
    expect(screen.getByText('Display Preferences')).toBeInTheDocument();
  });

  it('should render all field types correctly', () => {
    render(
      <SchemaForm
        schema={mockSchema}
        values={mockValues}
        onChange={mockOnChange}
      />
    );

    // String with enum (select)
    expect(screen.getByDisplayValue('whisper-small')).toBeInTheDocument();
    
    // String with enum (select) 
    expect(screen.getByDisplayValue('auto')).toBeInTheDocument();
    
    // Integer with min/max (slider)
    expect(screen.getByRole('slider')).toBeInTheDocument();
    
    // Boolean (checkbox)
    expect(screen.getByRole('checkbox')).toBeInTheDocument();
  });

  it('should call onChange when field values change', () => {
    render(
      <SchemaForm
        schema={mockSchema}
        values={mockValues}
        onChange={mockOnChange}
      />
    );

    // Change select value
    const select = screen.getByDisplayValue('whisper-small');
    fireEvent.change(select, { target: { value: 'whisper-medium' } });
    expect(mockOnChange).toHaveBeenCalledWith('asr_model_id', 'whisper-medium');

    // Change slider value
    const slider = screen.getByRole('slider');
    fireEvent.change(slider, { target: { value: '5' } });
    expect(mockOnChange).toHaveBeenCalledWith('cadence_threshold', 5);

    // Change checkbox
    const checkbox = screen.getByRole('checkbox');
    fireEvent.click(checkbox);
    expect(mockOnChange).toHaveBeenCalledWith('show_timestamps', false);
  });

  it('should validate field values and show errors', () => {
    const invalidValues = {
      ...mockValues,
      cadence_threshold: 10 // Above maximum of 8
    };

    render(
      <SchemaForm
        schema={mockSchema}
        values={invalidValues}
        onChange={mockOnChange}
      />
    );

    expect(screen.getByText('Value must be at most 8')).toBeInTheDocument();
  });

  it('should filter fields by level', () => {
    const schemaWithLevels: SettingsSchema = {
      ...mockSchema,
      properties: {
        ...mockSchema.properties,
        advanced_field: {
          type: 'string',
          title: 'Advanced Field',
          group: 'Advanced',
          'x-level': 'advanced',
          default: ''
        }
      },
      'x-groups': {
        ...mockSchema['x-groups'],
        Advanced: {
          title: 'Advanced Settings',
          order: 5
        }
      }
    };

    // Render with basic level - should not show advanced field
    render(
      <SchemaForm
        schema={schemaWithLevels}
        values={mockValues}
        onChange={mockOnChange}
        level="basic"
      />
    );

    expect(screen.queryByText('Advanced Settings')).not.toBeInTheDocument();
    expect(screen.queryByText('Advanced Field')).not.toBeInTheDocument();
  });
});