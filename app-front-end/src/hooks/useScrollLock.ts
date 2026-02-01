import { useEffect } from 'react';

/**
 * Lock body scroll when overlay/modal is open. Restore on cleanup.
 */
export function useScrollLock(open: boolean) {
  useEffect(() => {
    if (!open) return;
    const prev = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    return () => {
      document.body.style.overflow = prev;
    };
  }, [open]);
}
