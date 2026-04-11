import { useEffect } from 'react';

/**
 * Lock body scroll when overlay/modal is open.
 * Uses position:fixed trick to prevent iOS Safari scroll-bounce on the body.
 * Restores exact scroll position on cleanup.
 */
export function useScrollLock(open: boolean) {
  useEffect(() => {
    if (!open) return;
    const scrollY = window.scrollY;
    const orig = {
      overflow: document.body.style.overflow,
      position: document.body.style.position,
      top: document.body.style.top,
      width: document.body.style.width,
    };
    document.body.style.overflow = 'hidden';
    document.body.style.position = 'fixed';
    document.body.style.top = `-${scrollY}px`;
    document.body.style.width = '100%';
    return () => {
      document.body.style.overflow = orig.overflow;
      document.body.style.position = orig.position;
      document.body.style.top = orig.top;
      document.body.style.width = orig.width;
      window.scrollTo(0, scrollY);
    };
  }, [open]);
}
