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

// React StrictMode intentionally mounts effects twice in development. Keep the
// first authenticated read alive so both mounts observe one report snapshot.
let initialReport:
  | { userId: string; promise: Promise<ActivitySummary | null> }
  | undefined;

/**
 * Owns the away-window lifecycle for the signed-in app. It is mounted by the
 * app shell (not only by the home page), so returning to any workspace closes
 * the precise hidden-tab window and refreshes the report.
 */
export function useSinceAwaySummary(userId: string): ActivitySummary | null {
  const [summary, setSummary] = useState<ActivitySummary | null>(null);

  useEffect(() => {
    let cancelled = false;
    let boundaryWrite: Promise<void> = Promise.resolve();
    setSummary(null);

    const markBoundary = (keepalive = false, clearReport = true) => {
      if (!cancelled && clearReport) setSummary(null);
      boundaryWrite = markActivitySeen({ keepalive }).catch(() => {});
      return boundaryWrite;
    };

    const loadReport = async (source?: Promise<ActivitySummary | null>) => {
      // If the tab returned quickly, do not query until the hidden-at marker is
      // durable or we could accidentally include foreground work in the report.
      await boundaryWrite;
      try {
        const data = await (source ?? fetchActivitySummary());
        if (cancelled) return;
        if (!data) {
          setSummary(null);
          return;
        }
        if (!hasActivity(data)) {
          setSummary(null);
          return;
        }
        setSummary(data);
        // The displayed snapshot is now accounted for; subsequent activity
        // belongs to the next away window.
        void markBoundary(false, false);
      } catch {
        // The front door remains usable when the optional digest is unavailable.
      }
    };

    const arrivedFromLogin = Boolean(sessionStorage.getItem(LOGIN_ENTRY_SESSION_KEY));
    if (arrivedFromLogin || !initialReport || initialReport.userId !== userId) {
      initialReport = {
        userId,
        // LoginPage already displayed and acknowledges the same report on entry.
        promise: arrivedFromLogin
          ? Promise.resolve(null)
          : fetchActivitySummary().catch(() => null),
      };
    }
    void loadReport(initialReport.promise);

    const onVisibilityChange = () => {
      if (document.visibilityState === 'hidden') {
        void markBoundary(true);
      } else {
        void loadReport();
      }
    };

    document.addEventListener('visibilitychange', onVisibilityChange);
    return () => {
      cancelled = true;
      document.removeEventListener('visibilitychange', onVisibilityChange);
    };
  }, [userId]);

  return summary;
}
