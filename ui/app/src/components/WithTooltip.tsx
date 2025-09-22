import { ReactElement, cloneElement } from 'react';
import { Tooltip } from './Tooltip';

type XHelpProps = {
  'x-help'?: string | null;
};

export interface WithTooltipProps<T extends XHelpProps = XHelpProps> {
  children: ReactElement<T>;
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
export function WithTooltip<T extends XHelpProps = XHelpProps>({
  children,
  xHelp,
  placement = 'top',
  trigger = 'both',
}: WithTooltipProps<T>) {
  // Extract x-help from child element props if not provided explicitly
  const childProps = children.props as T;
  const { ['x-help']: childXHelp, ...propsWithoutXHelp } = childProps as T & XHelpProps;
  const helpFromChild = typeof childXHelp === 'string' ? childXHelp : undefined;
  const helpContent = xHelp ?? helpFromChild;

  // If no help content or it's empty/whitespace, return children as-is
  if (!helpContent || (typeof helpContent === 'string' && !helpContent.trim())) {
    return childXHelp !== undefined
      ? cloneElement(children, propsWithoutXHelp as Partial<T>)
      : children;
  }

  // Remove x-help from child props to avoid it appearing in DOM
  const cleanedChild = cloneElement(children, propsWithoutXHelp as Partial<T>);

  return (
    <Tooltip content={helpContent} placement={placement} trigger={trigger}>
      {cleanedChild}
    </Tooltip>
  );
}
