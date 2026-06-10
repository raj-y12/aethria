import { useEffect, useState } from 'react';
import { fetchActivitySummary, markActivitySeen, type ActivitySummary } from '../api/activity';
import { LOGIN_ENTRY_SESSION_KEY } from '../lib/loginEntryTransition';

/**
 * Module-level cache: the "since you were away" report is fetched once per
 * page load and marked seen immediately, but stays readable for the whole
 * session so navigating between workspaces doesn't make the line vanish.
 */
let cachedSinceAway: ActivitySummary | null | undefined;

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
 * What the agents did since the last visit — folded into the Today briefing
 * (this replaced the full-screen "While you were away" interstitial). Returns
 * null when there is nothing to report or the login screen already showed it.
 */
export function useSinceAwaySummary(): ActivitySummary | null {
  const [summary, setSummary] = useState<ActivitySummary | null>(cachedSinceAway ?? null);

  useEffect(() => {
    if (cachedSinceAway !== undefined) return;
    // Just signed in — LoginPage already presented the activity report.
    if (sessionStorage.getItem(LOGIN_ENTRY_SESSION_KEY)) {
      cachedSinceAway = null;
      return;
    }
    cachedSinceAway = null;
    let cancelled = false;
    fetchActivitySummary()
      .then((data) => {
        if (!hasActivity(data)) return;
        cachedSinceAway = data;
        if (!cancelled) setSummary(data);
        // Acknowledge immediately — the next visit starts a fresh report.
        markActivitySeen().catch(() => {});
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, []);

  return summary;
}
