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
        setShowSummary(true);
        setLoading(false);
      })
      .catch((err) => {
        if (cancelled) return;
        clearTimeout(timer);
        console.warn('[activity summary] fetch failed:', err);
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
