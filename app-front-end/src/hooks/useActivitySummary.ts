/**
 * Fetches pipeline activity since the user's last visit and determines
 * whether to show the "While you were away" summary screen.
 *
 * Shows the screen when:
 *   - Any metric > 0
 *   - AND the screen hasn't been shown yet in this browser session
 *
 * Re-shows if the tab was hidden for more than TAB_AWAY_THRESHOLD_MS and
 * new activity occurred.
 */
import { useState, useEffect, useCallback, useRef } from 'react';
import { fetchActivitySummary, ActivitySummary } from '../api/activity';

const SESSION_KEY = 'aethria_activity_shown';
const HIDDEN_AT_KEY = 'aethria_tab_hidden_at';
const TAB_AWAY_THRESHOLD_MS = 5 * 60 * 1000; // 5 minutes

function hasActivity(s: ActivitySummary): boolean {
  return s.found > 0 || s.reviewed > 0 || s.decided > 0 || s.escalations > 0;
}

export interface UseActivitySummaryResult {
  summary: ActivitySummary | null;
  showSummary: boolean;
  dismissSummary: () => void;
}

export function useActivitySummary(): UseActivitySummaryResult {
  const [summary, setSummary] = useState<ActivitySummary | null>(null);
  const [showSummary, setShowSummary] = useState(false);
  const fetchedOnMount = useRef(false);

  const checkActivity = useCallback(async () => {
    try {
      const data = await fetchActivitySummary();
      if (hasActivity(data)) {
        setSummary(data);
        setShowSummary(true);
        sessionStorage.setItem(SESSION_KEY, '1');
      }
    } catch {
      // silently ignore — non-critical feature
    }
  }, []);

  // On mount: fetch once if not already shown this session
  useEffect(() => {
    if (fetchedOnMount.current) return;
    fetchedOnMount.current = true;
    if (sessionStorage.getItem(SESSION_KEY)) return;
    checkActivity();
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
          // Clear the "shown" gate so we can show again if there's new activity
          sessionStorage.removeItem(SESSION_KEY);
          checkActivity();
        }
      }
    }
    document.addEventListener('visibilitychange', handleVisibilityChange);
    return () => document.removeEventListener('visibilitychange', handleVisibilityChange);
  }, [checkActivity]);

  const dismissSummary = useCallback(() => {
    setShowSummary(false);
  }, []);

  return { summary, showSummary, dismissSummary };
}
