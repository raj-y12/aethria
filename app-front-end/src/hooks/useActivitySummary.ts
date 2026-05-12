import { useState, useEffect, useCallback } from 'react';
import { fetchActivitySummary, markActivitySeen, ActivitySummary } from '../api/activity';

export interface UseActivitySummaryResult {
  loading: boolean;
  summary: ActivitySummary | null;
  showSummary: boolean;
  dismissSummary: () => void;
}

export function useActivitySummary(): UseActivitySummaryResult {
  const [loading, setLoading] = useState(true);
  const [summary, setSummary] = useState<ActivitySummary | null>(null);
  const [showSummary, setShowSummary] = useState(false);

  useEffect(() => {
    // Skip if we just logged in — LoginPage already showed the activity summary
    const justLoggedIn = sessionStorage.getItem('aethria_just_logged_in');
    if (justLoggedIn) {
      sessionStorage.removeItem('aethria_just_logged_in');
      setLoading(false);
      return;
    }

    let cancelled = false;

    // Safety valve: never block the app for more than 3s
    const timer = setTimeout(() => {
      if (!cancelled) setLoading(false);
    }, 3000);

    fetchActivitySummary()
      .then((data) => {
        if (cancelled) return;
        clearTimeout(timer);
        setSummary(data);
        const hasActivity =
          data.found > 0 ||
          data.reviewed > 0 ||
          (data.agent_decided ?? data.decided) > 0 ||
          (data.human_reviewed ?? 0) > 0 ||
          data.escalations > 0;
        setShowSummary(hasActivity);
        setLoading(false);
      })
      .catch(() => {
        if (cancelled) return;
        clearTimeout(timer);
        setLoading(false);
      });

    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, []); // runs once on mount

  const dismissSummary = useCallback(() => {
    setShowSummary(false);
    markActivitySeen().catch(() => {});
  }, []);

  return { loading, summary, showSummary, dismissSummary };
}
