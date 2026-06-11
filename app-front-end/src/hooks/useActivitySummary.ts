import { useEffect, useState } from 'react';
import { fetchActivitySummary, markActivitySeen, type ActivitySummary } from '../api/activity';
import { LOGIN_ENTRY_SESSION_KEY } from '../lib/loginEntryTransition';

function hasActivity(data: ActivitySummary): boolean {
  return (
    data.found > 0 ||
    data.reviewed > 0 ||
    (data.agent_decided ?? data.decided) > 0 ||
    (data.human_reviewed ?? 0) > 0 ||
    data.escalations > 0
  );
}

/**
 * Module-level single-flight: fetched once per page load, marked seen
 * immediately, and the result stays readable for the whole session (so
 * navigating between workspaces — or a StrictMode remount — doesn't lose it).
 */
let sinceAwayPromise: Promise<ActivitySummary | null> | undefined;

function loadSinceAwayOnce(): Promise<ActivitySummary | null> {
  if (sinceAwayPromise) return sinceAwayPromise;
  // Just signed in — LoginPage already presented the activity report.
  if (sessionStorage.getItem(LOGIN_ENTRY_SESSION_KEY)) {
    sinceAwayPromise = Promise.resolve(null);
    return sinceAwayPromise;
  }
  sinceAwayPromise = fetchActivitySummary()
    .then((data) => {
      if (!hasActivity(data)) return null;
      // Acknowledge immediately — the next visit starts a fresh report.
      markActivitySeen().catch(() => {});
      return data;
    })
    .catch(() => null);
  return sinceAwayPromise;
}

/**
 * What the agents did since the last visit — shown on the front door (this
 * replaced the full-screen "While you were away" interstitial). Returns null
 * when there is nothing to report or the login screen already showed it.
 */
export function useSinceAwaySummary(): ActivitySummary | null {
  const [summary, setSummary] = useState<ActivitySummary | null>(null);

  useEffect(() => {
    let cancelled = false;
    void loadSinceAwayOnce().then((data) => {
      if (!cancelled && data) setSummary(data);
    });
    return () => {
      cancelled = true;
    };
  }, []);

  return summary;
}
