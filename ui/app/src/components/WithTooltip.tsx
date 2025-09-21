import { ReactElement, cloneElement } from 'react';
import { Tooltip } from './Tooltip';

export interface WithTooltipProps {
  children: ReactElement;
  xHelp?: string;
  placement?: 'top' | 'bottom' | 'left' | 'right';
  trigger?: 'hover' | 'focus' | 'both';
}

/**
 * WithTooltip component that wraps any element and provides tooltip functionality
 * based on x-help attribute or explicit content.
 * 
 * Usage:
 * <WithTooltip xHelp="This is helpful information">
 *   <button>Click me</button>
 * </WithTooltip>
 * 
 * Or with x-help attribute on the child:
 * <WithTooltip>
 *   <button x-help="This is helpful information">Click me</button>
 * </WithTooltip>
 */
export function WithTooltip({
  children,
  xHelp,
  placement = 'top',
  trigger = 'both',
}: WithTooltipProps) {
  // Extract x-help from child element props if not provided explicitly
  const childProps = children.props as any;
  const helpContent = xHelp || childProps['x-help'];

  // If no help content or it's empty/whitespace, return children as-is
  if (!helpContent || (typeof helpContent === 'string' && !helpContent.trim())) {
    // Still need to remove x-help attribute if it exists
    if (childProps['x-help']) {
      const cleanedProps = { ...childProps };
      delete cleanedProps['x-help'];
      return cloneElement(children, cleanedProps);
    }
    return children;
  }

  // Remove x-help from child props to avoid it appearing in DOM
  const cleanedProps = { ...childProps };
  delete cleanedProps['x-help'];
  const cleanedChild = cloneElement(children, cleanedProps);

  return (
    <Tooltip content={helpContent} placement={placement} trigger={trigger}>
      {cleanedChild}
    </Tooltip>
  );
}