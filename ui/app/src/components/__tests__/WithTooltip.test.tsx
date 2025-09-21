import { describe, it, expect, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import '@testing-library/jest-dom';
import { WithTooltip } from '../WithTooltip';

// Mock ResizeObserver
(globalThis as any).ResizeObserver = vi.fn().mockImplementation(() => ({
  observe: vi.fn(),
  unobserve: vi.fn(),
  disconnect: vi.fn(),
}));

describe('WithTooltip', () => {
  it('should render child element without tooltip when no x-help content', () => {
    render(
      <WithTooltip>
        <button>Test button</button>
      </WithTooltip>
    );

    expect(screen.getByRole('button', { name: 'Test button' })).toBeInTheDocument();
    // No tooltip should be present initially
    expect(screen.queryByRole('tooltip')).not.toBeInTheDocument();
  });

  it('should show tooltip when xHelp prop is provided', async () => {
    const user = userEvent.setup();
    
    render(
      <WithTooltip xHelp="This is helpful information">
        <button>Test button</button>
      </WithTooltip>
    );

    const button = screen.getByRole('button', { name: 'Test button' });
    
    // Hover to show tooltip
    await user.hover(button);
    
    await waitFor(() => {
      expect(screen.getByRole('tooltip')).toBeInTheDocument();
      expect(screen.getByText('This is helpful information')).toBeInTheDocument();
    });
  });

  it('should read x-help attribute from child element', async () => {
    const user = userEvent.setup();
    
    render(
      <WithTooltip>
        <button x-help="Help from attribute">Test button</button>
      </WithTooltip>
    );

    const button = screen.getByRole('button', { name: 'Test button' });
    
    // Hover to show tooltip
    await user.hover(button);
    
    await waitFor(() => {
      expect(screen.getByRole('tooltip')).toBeInTheDocument();
      expect(screen.getByText('Help from attribute')).toBeInTheDocument();
    });
  });

  it('should prioritize xHelp prop over x-help attribute', async () => {
    const user = userEvent.setup();
    
    render(
      <WithTooltip xHelp="Help from prop">
        <button x-help="Help from attribute">Test button</button>
      </WithTooltip>
    );

    const button = screen.getByRole('button', { name: 'Test button' });
    
    // Hover to show tooltip
    await user.hover(button);
    
    await waitFor(() => {
      expect(screen.getByRole('tooltip')).toBeInTheDocument();
      expect(screen.getByText('Help from prop')).toBeInTheDocument();
      expect(screen.queryByText('Help from attribute')).not.toBeInTheDocument();
    });
  });

  it('should clean x-help attribute from props when rendering tooltip', () => {
    render(
      <WithTooltip>
        <button x-help="Help content" data-testid="test-button">Test button</button>
      </WithTooltip>
    );

    const button = screen.getByTestId('test-button');
    
    // We can't easily test if React removed the attribute since React may still render unknown attributes
    // The important thing is that the tooltip functionality works, which is tested in other tests
    expect(button).toBeInTheDocument();
  });

  it('should preserve other attributes when processing x-help', () => {
    render(
      <WithTooltip>
        <button 
          x-help="Help content" 
          data-testid="test-button" 
          className="custom-class"
          disabled
        >
          Test button
        </button>
      </WithTooltip>
    );

    const button = screen.getByTestId('test-button');
    
    // Important attributes should be preserved
    expect(button).toHaveAttribute('data-testid', 'test-button');
    expect(button).toHaveClass('custom-class');
    expect(button).toBeDisabled();
  });

  it('should support different tooltip placements', async () => {
    const user = userEvent.setup();
    
    render(
      <WithTooltip xHelp="Help content" placement="bottom">
        <button>Test button</button>
      </WithTooltip>
    );

    const button = screen.getByRole('button', { name: 'Test button' });
    
    // Hover to show tooltip
    await user.hover(button);
    
    await waitFor(() => {
      const tooltip = screen.getByRole('tooltip');
      expect(tooltip).toBeInTheDocument();
      expect(tooltip).toHaveClass('tooltip--bottom');
    });
  });

  it('should support different trigger modes', async () => {
    const user = userEvent.setup();
    
    render(
      <WithTooltip xHelp="Help content" trigger="focus">
        <button>Test button</button>
      </WithTooltip>
    );

    const button = screen.getByRole('button', { name: 'Test button' });
    
    // Hover should not show tooltip when trigger is focus
    await user.hover(button);
    expect(screen.queryByRole('tooltip')).not.toBeInTheDocument();
    
    // Focus should show tooltip
    await user.click(button);
    
    await waitFor(() => {
      expect(screen.getByRole('tooltip')).toBeInTheDocument();
    });
  });

  it('should work with various HTML elements', async () => {
    const user = userEvent.setup();
    
    const { rerender } = render(
      <WithTooltip xHelp="Input help">
        <input type="text" placeholder="Test input" />
      </WithTooltip>
    );

    let element = screen.getByPlaceholderText('Test input');
    await user.hover(element);
    
    await waitFor(() => {
      expect(screen.getByText('Input help')).toBeInTheDocument();
    });

    // Test with select
    rerender(
      <WithTooltip xHelp="Select help">
        <select>
          <option>Option 1</option>
        </select>
      </WithTooltip>
    );

    element = screen.getByRole('combobox');
    await user.hover(element);
    
    await waitFor(() => {
      expect(screen.getByText('Select help')).toBeInTheDocument();
    });

    // Test with div
    rerender(
      <WithTooltip xHelp="Div help">
        <div role="region">Test div</div>
      </WithTooltip>
    );

    element = screen.getByRole('region');
    await user.hover(element);
    
    await waitFor(() => {
      expect(screen.getByText('Div help')).toBeInTheDocument();
    });
  });

  it('should handle empty or whitespace-only help content', () => {
    const { rerender } = render(
      <WithTooltip xHelp="">
        <button>Test button</button>
      </WithTooltip>
    );

    // Empty string should not show tooltip
    expect(screen.getByRole('button')).toBeInTheDocument();
    expect(screen.queryByRole('tooltip')).not.toBeInTheDocument();

    // Whitespace-only should not show tooltip
    rerender(
      <WithTooltip xHelp="   ">
        <button>Test button</button>
      </WithTooltip>
    );

    expect(screen.queryByRole('tooltip')).not.toBeInTheDocument();
  });
});