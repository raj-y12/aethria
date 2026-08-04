import { useEffect, RefObject } from 'react';

const FOCUSABLE =
  'button:not(:disabled), [href], input:not(:disabled), select:not(:disabled), textarea:not(:disabled), [tabindex]:not([tabindex="-1"]):not(:disabled)';

function getFocusables(container: HTMLElement): HTMLElement[] {
  return Array.from(container.querySelectorAll<HTMLElement>(FOCUSABLE));
}

function focusContainer(container: HTMLElement) {
  if (!container.hasAttribute('tabindex')) container.tabIndex = -1;
  container.focus();
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
    if (focusables.length === 0) {
      focusContainer(el);
    } else {
      focusables[0].focus();
    }

    const handle = (e: KeyboardEvent) => {
      if (e.key !== 'Tab') return;
      const liveFocusables = getFocusables(el);
      if (liveFocusables.length === 0) {
        e.preventDefault();
        focusContainer(el);
        return;
      }
      const firstFocusable = liveFocusables[0];
      const lastFocusable = liveFocusables[liveFocusables.length - 1];
      const current = document.activeElement as HTMLElement | null;
      if (!current || !el.contains(current)) {
        if (!e.shiftKey) {
          e.preventDefault();
          firstFocusable.focus();
        }
        return;
      }

      if (e.shiftKey) {
        if (current === firstFocusable) {
          e.preventDefault();
          lastFocusable.focus();
        }
      } else {
        if (current === lastFocusable) {
          e.preventDefault();
          firstFocusable.focus();
        }
      }
    };

    document.addEventListener('keydown', handle);
    return () => document.removeEventListener('keydown', handle);
  }, [enabled, containerRef]);
}
