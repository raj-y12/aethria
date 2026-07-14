import { useEffect, useRef } from 'react';

const REFRESH_COOLDOWN_MS = 1_000;
const AGENT_WAKE_COOLDOWN_MS = 60_000;

interface ForegroundSyncOptions {
  refresh: () => void;
  wakeAgents: () => void;
  enabled?: boolean;
}

/**
 * Refresh active data whenever this tab becomes usable again. Browsers commonly
 * emit visibilitychange, focus, and online together, so reads are coalesced and
 * the more expensive agent wake-up is limited to the backend's one-minute
 * trigger window.
 */
export function useForegroundSync({
  refresh,
  wakeAgents,
  enabled = true,
}: ForegroundSyncOptions): void {
  const refreshRef = useRef(refresh);
  const wakeAgentsRef = useRef(wakeAgents);
  const lastRefreshAt = useRef(Number.NEGATIVE_INFINITY);
  const lastAgentWakeAt = useRef(Number.NEGATIVE_INFINITY);

  refreshRef.current = refresh;
  wakeAgentsRef.current = wakeAgents;

  useEffect(() => {
    if (!enabled || typeof window === 'undefined' || typeof document === 'undefined') return;

    const sync = () => {
      if (document.visibilityState !== 'visible') return;
      const now = Date.now();
      if (now - lastRefreshAt.current >= REFRESH_COOLDOWN_MS) {
        lastRefreshAt.current = now;
        refreshRef.current();
      }
      if (now - lastAgentWakeAt.current >= AGENT_WAKE_COOLDOWN_MS) {
        lastAgentWakeAt.current = now;
        wakeAgentsRef.current();
      }
    };

    document.addEventListener('visibilitychange', sync);
    window.addEventListener('focus', sync);
    window.addEventListener('online', sync);
    window.addEventListener('pageshow', sync);
    return () => {
      document.removeEventListener('visibilitychange', sync);
      window.removeEventListener('focus', sync);
      window.removeEventListener('online', sync);
      window.removeEventListener('pageshow', sync);
    };
  }, [enabled]);
}
