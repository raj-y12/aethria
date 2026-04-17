/**
 * Fetches pipeline activity since the user's last visit.
 *
 * `loading` is true until the fetch resolves (or times out after 2s).
 * Consumers should gate app rendering on `!loading` so the summary
 * appears before any other content.
 *
 * Re-shows if the tab was hidden for more than TAB_AWAY_THRESHOLD_MS
 * and new activity occurred since then.
 */
import { useState, useEffect, useCallback, useRef } from 'react';
import { fetchActivitySummary, ActivitySummary } from '../api/activity';

const SESSION_KEY = 'aethria_activity_shown';
const HIDDEN_AT_KEY = 'aethria_tab_hidden_at';
const TAB_AWAY_THRESHOLD_MS = 5 * 60 * 1000; // 5 minutes
const FETCH_TIMEOUT_MS = 2000;

function hasActivity(s: ActivitySummary): boolean {
  return s.found > 0 || s.reviewed > 0 || s.decided > 0 || s.escalations > 0;
}

export interface UseActivitySummaryResult {
  summary: ActivitySummary | null;
  showSummary: boolean;
  loading: boolean;
  dismissSummary: () => void;
}

export function useActivitySummary(): UseActivitySummaryResult {
  const [summary, setSummary] = useState<ActivitySummary | null>(null);
  const [showSummary, setShowSummary] = useState(false);
  // Start loading=true so the app is gated until we know whether to show the modal
  const [loading, setLoading] = useState(true);
  const fetchedOnMount = useRef(false);

  const checkActivity = useCallback(async (gateApp = false) => {
    // Safety timeout: never block the app for more than FETCH_TIMEOUT_MS
    const timeout = gateApp
      ? setTimeout(() => setLoading(false), FETCH_TIMEOUT_MS)
      : undefined;

    try {
      const data = await fetchActivitySummary();
      clearTimeout(timeout);
      if (hasActivity(data)) {
        setSummary(data);
        setShowSummary(true);
        sessionStorage.setItem(SESSION_KEY, '1');
      }
    } catch (err) {
      console.warn('[useActivitySummary] fetch failed:', err);
      clearTimeout(timeout);
    } finally {
      if (gateApp) setLoading(false);
    }
  }, []);

  // On mount: gate the app render, fetch once if not shown this session
  useEffect(() => {
    if (fetchedOnMount.current) return;
    fetchedOnMount.current = true;

    if (sessionStorage.getItem(SESSION_KEY)) {
      // Already shown this session — ungate immediately
      setLoading(false);
      return;
    }

    checkActivity(true);
  }, [checkActivity]);

  // On tab visibility change: re-check if away long enough
  useEffect(() => {
    function handleVisibilityChange() {
      if (document.visibilityState === 'hidden') {
        sessionStorage.setItem(HIDDEN_AT_KEY, String(Date.now()));
      } else {
        const hiddenAt = Number(sessionStorage.getItem(HIDDEN_AT_KEY) ?? 0);
        const awayMs = Date.now() - hiddenAt;
        if (hiddenAt > 0 && awayMs >= TAB_AWAY_THRESHOLD_MS) {
          sessionStorage.removeItem(SESSION_KEY);
          checkActivity(false);
        }
      }
    }
    document.addEventListener('visibilitychange', handleVisibilityChange);
    return () => document.removeEventListener('visibilitychange', handleVisibilityChange);
  }, [checkActivity]);

  const dismissSummary = useCallback(() => {
    setShowSummary(false);
  }, []);

  return { summary, showSummary, loading, dismissSummary };
}
