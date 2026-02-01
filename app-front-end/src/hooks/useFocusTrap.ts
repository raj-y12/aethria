import { useEffect, RefObject } from 'react';

const FOCUSABLE =
  'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])';

function getFocusables(container: HTMLElement): HTMLElement[] {
  return Array.from(container.querySelectorAll<HTMLElement>(FOCUSABLE));
}

/**
 * Trap focus inside container when enabled. Focus first focusable on mount.
 * Wrap Tab/Shift+Tab within container.
 */
export function useFocusTrap(
  enabled: boolean,
  containerRef: RefObject<HTMLElement | null>
) {
  useEffect(() => {
    if (!enabled || !containerRef.current) return;
    const el = containerRef.current;
    const focusables = getFocusables(el);
    if (focusables.length === 0) return;

    const first = focusables[0];
    const last = focusables[focusables.length - 1];
    first.focus();

    const handle = (e: KeyboardEvent) => {
      if (e.key !== 'Tab') return;
      const current = document.activeElement as HTMLElement | null;
      if (!current || !el.contains(current)) return;

      if (e.shiftKey) {
        if (current === first) {
          e.preventDefault();
          last.focus();
        }
      } else {
        if (current === last) {
          e.preventDefault();
          first.focus();
        }
      }
    };

    document.addEventListener('keydown', handle);
    return () => document.removeEventListener('keydown', handle);
  }, [enabled, containerRef]);
}
