import { useEffect, useRef, useCallback, useState } from 'react';

export function useAutoScroll(ref: React.RefObject<HTMLElement>) {
  const [paused, setPaused] = useState(false);
  const threshold = 16; // px
  const jumpToLive = useCallback(() => {
    if (ref.current) {
      ref.current.scrollTop = ref.current.scrollHeight;
      setPaused(false);
    }
  }, [ref]);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    function onScroll() {
      const nearBottom = el.scrollHeight - el.scrollTop - el.clientHeight < threshold;
      setPaused(!nearBottom);
    }
    el.addEventListener('scroll', onScroll);
    return () => el.removeEventListener('scroll', onScroll);
  }, [ref]);

  return { paused, jumpToLive };
}
