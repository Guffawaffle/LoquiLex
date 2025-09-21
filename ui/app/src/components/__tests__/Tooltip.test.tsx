import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import '@testing-library/jest-dom';
import { Tooltip } from '../Tooltip';

// Mock ResizeObserver
(globalThis as any).ResizeObserver = vi.fn().mockImplementation(() => ({
  observe: vi.fn(),
  unobserve: vi.fn(),
  disconnect: vi.fn(),
}));

describe('Tooltip', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('should render trigger element', () => {
    render(
      <Tooltip content="Test tooltip">
        <button>Test button</button>
      </Tooltip>
    );

    expect(screen.getByRole('button', { name: 'Test button' })).toBeInTheDocument();
  });

  it('should show tooltip on hover by default', async () => {
    const user = userEvent.setup();
    
    render(
      <Tooltip content="Test tooltip">
        <button>Test button</button>
      </Tooltip>
    );

    const button = screen.getByRole('button', { name: 'Test button' });
    
    // Hover over the button
    await user.hover(button);
    
    await waitFor(() => {
      expect(screen.getByRole('tooltip')).toBeInTheDocument();
      expect(screen.getByText('Test tooltip')).toBeInTheDocument();
    });

    // Move away to hide tooltip
    await user.unhover(button);
    
    await waitFor(() => {
      expect(screen.queryByRole('tooltip')).not.toBeInTheDocument();
    });
  });

  it('should show tooltip on focus by default', async () => {
    const user = userEvent.setup();
    
    render(
      <Tooltip content="Test tooltip">
        <button>Test button</button>
      </Tooltip>
    );

    const button = screen.getByRole('button', { name: 'Test button' });
    
    // Focus the button
    await user.click(button);
    
    await waitFor(() => {
      expect(screen.getByRole('tooltip')).toBeInTheDocument();
      expect(screen.getByText('Test tooltip')).toBeInTheDocument();
    });

    // Blur to hide tooltip
    button.blur();
    
    await waitFor(() => {
      expect(screen.queryByRole('tooltip')).not.toBeInTheDocument();
    });
  });

  it('should only show tooltip on hover when trigger is "hover"', async () => {
    const user = userEvent.setup();
    
    render(
      <Tooltip content="Test tooltip" trigger="hover">
        <button>Test button</button>
      </Tooltip>
    );

    const button = screen.getByRole('button', { name: 'Test button' });
    
    // Focus should not show tooltip when trigger is hover only
    button.focus();
    await waitFor(() => {
      expect(screen.queryByRole('tooltip')).not.toBeInTheDocument();
    }, { timeout: 100 });
    
    // But hover should show tooltip
    await user.hover(button);
    
    await waitFor(() => {
      expect(screen.getByRole('tooltip')).toBeInTheDocument();
    });
  });

  it('should only show tooltip on focus when trigger is "focus"', async () => {
    const user = userEvent.setup();
    
    render(
      <Tooltip content="Test tooltip" trigger="focus">
        <button>Test button</button>
      </Tooltip>
    );

    const button = screen.getByRole('button', { name: 'Test button' });
    
    // Hover should not show tooltip when trigger is focus only
    await user.hover(button);
    await waitFor(() => {
      expect(screen.queryByRole('tooltip')).not.toBeInTheDocument();
    }, { timeout: 100 });
    
    // But focus should show tooltip
    button.focus();
    
    await waitFor(() => {
      expect(screen.getByRole('tooltip')).toBeInTheDocument();
    });
  });

  it('should hide tooltip on Escape key', async () => {
    const user = userEvent.setup();
    
    render(
      <Tooltip content="Test tooltip">
        <button>Test button</button>
      </Tooltip>
    );

    const button = screen.getByRole('button', { name: 'Test button' });
    
    // Show tooltip
    await user.hover(button);
    
    await waitFor(() => {
      expect(screen.getByRole('tooltip')).toBeInTheDocument();
    });

    // Focus the button first to ensure keyboard events are captured
    button.focus();
    
    // Press Escape to hide
    fireEvent.keyDown(button, { key: 'Escape', code: 'Escape' });
    
    await waitFor(() => {
      expect(screen.queryByRole('tooltip')).not.toBeInTheDocument();
    }, { timeout: 200 });
  });

  it('should set correct ARIA attributes', async () => {
    const user = userEvent.setup();
    
    render(
      <Tooltip content="Test tooltip">
        <button>Test button</button>
      </Tooltip>
    );

    const button = screen.getByRole('button', { name: 'Test button' });
    
    // Initially no aria-describedby
    expect(button).not.toHaveAttribute('aria-describedby');
    
    // Show tooltip
    await user.hover(button);
    
    await waitFor(() => {
      const tooltip = screen.getByRole('tooltip');
      expect(tooltip).toBeInTheDocument();
      expect(tooltip).toHaveAttribute('role', 'tooltip');
      expect(tooltip).toHaveAttribute('aria-hidden', 'false');
      
      // Button should now have aria-describedby pointing to tooltip
      const tooltipId = tooltip.getAttribute('id');
      expect(button).toHaveAttribute('aria-describedby', tooltipId);
    });
  });

  it('should support different placements', () => {
    const { rerender } = render(
      <Tooltip content="Test tooltip" placement="top">
        <button>Test button</button>
      </Tooltip>
    );

    // We can't easily test positioning without DOM layout, but we can test CSS classes
    rerender(
      <Tooltip content="Test tooltip" placement="bottom">
        <button>Test button</button>
      </Tooltip>
    );

    rerender(
      <Tooltip content="Test tooltip" placement="left">
        <button>Test button</button>
      </Tooltip>
    );

    rerender(
      <Tooltip content="Test tooltip" placement="right">
        <button>Test button</button>
      </Tooltip>
    );
    
    // If we get here without errors, placement prop is being handled
    expect(screen.getByRole('button')).toBeInTheDocument();
  });

  it('should use custom id when provided', async () => {
    const user = userEvent.setup();
    const customId = 'my-custom-tooltip';
    
    render(
      <Tooltip content="Test tooltip" id={customId}>
        <button>Test button</button>
      </Tooltip>
    );

    const button = screen.getByRole('button', { name: 'Test button' });
    
    // Show tooltip
    await user.hover(button);
    
    await waitFor(() => {
      const tooltip = screen.getByRole('tooltip');
      expect(tooltip).toHaveAttribute('id', customId);
      expect(button).toHaveAttribute('aria-describedby', customId);
    });
  });

  it('should handle long tooltip content', async () => {
    const user = userEvent.setup();
    const longContent = 'This is a very long tooltip content that should wrap properly and not break the layout or cause any issues with positioning or accessibility.';
    
    render(
      <Tooltip content={longContent}>
        <button>Test button</button>
      </Tooltip>
    );

    const button = screen.getByRole('button', { name: 'Test button' });
    
    // Show tooltip
    await user.hover(button);
    
    await waitFor(() => {
      expect(screen.getByText(longContent)).toBeInTheDocument();
    });
  });
});