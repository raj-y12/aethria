import { useEffect, useRef, useCallback } from 'react';

const ACTIVITY_EVENTS = ['mousedown', 'keydown', 'scroll', 'touchstart', 'mousemove'] as const;

interface UseIdleTimeoutOptions {
  /** Time in ms before idle callback fires. */
  timeoutMs: number;
  /** Callback when idle timeout is reached. */
  onIdle: () => void;
  /** Called on each activity to persist timestamp (e.g. to localStorage). */
  onActivity?: (now: number) => void;
  /** Whether the hook is active. */
  enabled?: boolean;
}

/**
 * Fires onIdle after timeoutMs of no user activity.
 * Resets the timer on mousedown, keydown, scroll, touchstart, mousemove.
 */
export function useIdleTimeout({
  timeoutMs,
  onIdle,
  onActivity,
  enabled = true,
}: UseIdleTimeoutOptions): void {
  const timeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const onIdleRef = useRef(onIdle);
  const onActivityRef = useRef(onActivity);
  onIdleRef.current = onIdle;
  onActivityRef.current = onActivity;

  const resetTimer = useCallback(() => {
    const now = Date.now();
    onActivityRef.current?.(now);
    if (timeoutRef.current) clearTimeout(timeoutRef.current);
    timeoutRef.current = setTimeout(() => {
      timeoutRef.current = null;
      onIdleRef.current();
    }, timeoutMs);
  }, [timeoutMs]);

  useEffect(() => {
    if (!enabled) return;
    resetTimer();
    ACTIVITY_EVENTS.forEach((e) => window.addEventListener(e, resetTimer));
    return () => {
      if (timeoutRef.current) clearTimeout(timeoutRef.current);
      ACTIVITY_EVENTS.forEach((e) => window.removeEventListener(e, resetTimer));
    };
  }, [enabled, resetTimer]);
}
