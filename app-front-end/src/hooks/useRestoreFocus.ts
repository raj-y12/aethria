import { useEffect, RefObject, useRef } from 'react';

/**
 * When `open` goes from true to false, focus `restoreRef.current`.
 * Caller sets restoreRef.current (e.g. document.activeElement) before opening.
 * If `onlyWhen` is false, skip restore (e.g. another overlay still open).
 */
export function useRestoreFocus(
  open: boolean,
  restoreRef: RefObject<HTMLElement | null>,
  onlyWhen: boolean = true
) {
  const prevOpen = useRef(open);
  useEffect(() => {
    const wasOpen = prevOpen.current;
    prevOpen.current = open;
    if (wasOpen && !open && onlyWhen) {
      const target = restoreRef.current;
      if (target && typeof target.focus === 'function') {
        target.focus();
      }
    }
  }, [open, restoreRef, onlyWhen]);
}
