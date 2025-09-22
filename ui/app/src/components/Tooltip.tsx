import React, { useState, useRef, useEffect, ReactNode } from 'react';

export interface TooltipProps {
  children: ReactNode;
  content: string;
  placement?: 'top' | 'bottom' | 'left' | 'right';
  trigger?: 'hover' | 'focus' | 'both';
  id?: string;
}

export function Tooltip({
  children,
  content,
  placement = 'top',
  trigger = 'both',
  id,
}: TooltipProps) {
  const [isVisible, setIsVisible] = useState(false);
  const [position, setPosition] = useState({ x: 0, y: 0 });
  const triggerRef = useRef<HTMLDivElement>(null);
  const tooltipRef = useRef<HTMLDivElement>(null);
  const tooltipId = id || `tooltip-${Math.random().toString(36).substring(2, 11)}`;

  const updatePosition = () => {
    if (!triggerRef.current || !tooltipRef.current) return;

    const triggerRect = triggerRef.current.getBoundingClientRect();
    const tooltipRect = tooltipRef.current.getBoundingClientRect();
    const scrollX = window.scrollX;
    const scrollY = window.scrollY;

    let x = 0;
    let y = 0;

    switch (placement) {
      case 'top':
        x = scrollX + triggerRect.left + triggerRect.width / 2 - tooltipRect.width / 2;
        y = scrollY + triggerRect.top - tooltipRect.height - 8;
        break;
      case 'bottom':
        x = scrollX + triggerRect.left + triggerRect.width / 2 - tooltipRect.width / 2;
        y = scrollY + triggerRect.bottom + 8;
        break;
      case 'left':
        x = scrollX + triggerRect.left - tooltipRect.width - 8;
        y = scrollY + triggerRect.top + triggerRect.height / 2 - tooltipRect.height / 2;
        break;
      case 'right':
        x = scrollX + triggerRect.right + 8;
        y = scrollY + triggerRect.top + triggerRect.height / 2 - tooltipRect.height / 2;
        break;
    }

    // Keep tooltip within viewport bounds
    x = Math.max(8, Math.min(x, window.innerWidth - tooltipRect.width - 8));
    y = Math.max(8, Math.min(y, window.innerHeight - tooltipRect.height - 8));

    setPosition({ x, y });
  };

  const showTooltip = () => {
    setIsVisible(true);
  };

  const hideTooltip = () => {
    setIsVisible(false);
  };

  const handleMouseEnter = () => {
    if (trigger === 'hover' || trigger === 'both') {
      showTooltip();
    }
  };

  const handleMouseLeave = () => {
    if (trigger === 'hover' || trigger === 'both') {
      hideTooltip();
    }
  };

  const handleFocus = () => {
    if (trigger === 'focus' || trigger === 'both') {
      showTooltip();
    }
  };

  const handleBlur = () => {
    if (trigger === 'focus' || trigger === 'both') {
      hideTooltip();
    }
  };

  const handleKeyDown = (event: React.KeyboardEvent) => {
    if (event.key === 'Escape' && isVisible) {
      hideTooltip();
      event.preventDefault();
    }
  };

  useEffect(() => {
    if (isVisible) {
      updatePosition();
      
      const handleResize = () => updatePosition();
      const handleScroll = () => updatePosition();
      
      window.addEventListener('resize', handleResize);
      window.addEventListener('scroll', handleScroll);
      
      return () => {
        window.removeEventListener('resize', handleResize);
        window.removeEventListener('scroll', handleScroll);
      };
    }
  }, [isVisible, placement]);

  // Clone children to add event handlers and ARIA attributes
  type TooltipEventHandlers = {
    onMouseEnter?: React.MouseEventHandler;
    onMouseLeave?: React.MouseEventHandler;
    onFocus?: React.FocusEventHandler;
    onBlur?: React.FocusEventHandler;
    onKeyDown?: React.KeyboardEventHandler;
  };
  const eventHandlers: TooltipEventHandlers = {};
  
  if (trigger === 'hover' || trigger === 'both') {
    eventHandlers.onMouseEnter = (e: React.MouseEvent) => {
      handleMouseEnter();
      const originalHandler = (children as React.ReactElement).props.onMouseEnter;
      if (originalHandler) originalHandler(e);
    };
    eventHandlers.onMouseLeave = (e: React.MouseEvent) => {
      handleMouseLeave();
      const originalHandler = (children as React.ReactElement).props.onMouseLeave;
      if (originalHandler) originalHandler(e);
    };
  }
  
  if (trigger === 'focus' || trigger === 'both') {
    eventHandlers.onFocus = (e: React.FocusEvent) => {
      handleFocus();
      const originalHandler = (children as React.ReactElement).props.onFocus;
      if (originalHandler) originalHandler(e);
    };
    eventHandlers.onBlur = (e: React.FocusEvent) => {
      handleBlur();
      const originalHandler = (children as React.ReactElement).props.onBlur;
      if (originalHandler) originalHandler(e);
    };
  }

  eventHandlers.onKeyDown = (e: React.KeyboardEvent) => {
    handleKeyDown(e);
    const originalHandler = (children as React.ReactElement).props.onKeyDown;
    if (originalHandler) originalHandler(e);
  };

  const enhancedChildren = React.cloneElement(children as React.ReactElement, {
    ...eventHandlers,
    'aria-describedby': isVisible ? tooltipId : undefined,
  });

  return (
    <div ref={triggerRef} style={{ display: 'inline-block' }}>
      {enhancedChildren}
      {isVisible && (
        <div
          ref={tooltipRef}
          id={tooltipId}
          role="tooltip"
          className={`tooltip tooltip--${placement}`}
          style={{
            position: 'absolute',
            left: position.x,
            top: position.y,
            zIndex: 1000,
          }}
          aria-hidden={!isVisible}
        >
          {content}
        </div>
      )}
    </div>
  );
}