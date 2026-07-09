/**
 * Warm start: persist the last-known deal-flow snapshot per user in
 * localStorage and prime the query cache with it on the next login, so the
 * home page (headline + the four doors) paints instantly instead of waiting
 * on the backend.
 *
 * No extra requests are made: hydrated entries keep their original
 * `dataUpdatedAt`, so TanStack Query's normal staleness rules decide whether a
 * background refetch happens. STATIC-intent queries (which never refetch on
 * mount) get one idle-only invalidate so a stale snapshot still refreshes —
 * anything already in flight is skipped, never duplicated.
 */
import { useEffect, useRef } from 'react';
import { useAuth } from '@clerk/react-router';
import { useQueryClient, type QueryClient } from '@tanstack/react-query';

const VERSION = 1;
const STORAGE_PREFIX = `aethria:warm:v${VERSION}:`;
/** Snapshots older than this trigger a background refresh of STATIC queries. */
const FRESH_MS = 90_000;
const WRITE_DEBOUNCE_MS = 2_000;

/** List-level keys the home page + workspaces need for first paint. */
const WARM_KEYS: readonly (readonly string[])[] = [
  ['startups', 'list'],
  ['escalations'],
  ['signals'],
  ['analytics', 'watchlist'],
  ['fund-thesis', 'runtime'],
  ['settings'],
];

const storageKey = (userId: string) => `${STORAGE_PREFIX}${userId}`;

export function clearWarmStartSnapshots(): void {
  try {
    for (let i = sessionStorage.length - 1; i >= 0; i -= 1) {
      const key = sessionStorage.key(i);
      if (key?.startsWith(STORAGE_PREFIX)) sessionStorage.removeItem(key);
    }
  } catch {
    // Session storage may be unavailable in hardened/private browser modes.
  }
}

type Snapshot = { at: number; entries: [readonly string[], unknown][] };

export function hydrateWarmStart(queryClient: QueryClient, userId: string): void {
  try {
    const raw = sessionStorage.getItem(storageKey(userId));
    if (!raw) return;
    const snapshot = JSON.parse(raw) as Snapshot;
    if (!snapshot || !Array.isArray(snapshot.entries)) return;
    for (const [key, data] of snapshot.entries) {
      if (data === undefined || data === null) continue;
      // Keep the snapshot's real age so normal staleness rules apply.
      queryClient.setQueryData(key as string[], data, { updatedAt: snapshot.at });
    }
  } catch {
    // Corrupt or inaccessible storage — cold load, same as today.
  }
}

export function persistWarmSnapshot(queryClient: QueryClient, userId: string): void {
  try {
    const entries: Snapshot['entries'] = [];
    for (const key of WARM_KEYS) {
      const data = queryClient.getQueryData(key as string[]);
      if (data !== undefined) entries.push([key, data]);
    }
    if (entries.length === 0) return;
    sessionStorage.setItem(storageKey(userId), JSON.stringify({ at: Date.now(), entries }));
  } catch {
    // Quota exceeded / private mode — skip; warm start is best-effort.
  }
}

/** Age of the stored snapshot in ms, or null when absent/corrupt. */
function snapshotAge(userId: string): number | null {
  try {
    const raw = sessionStorage.getItem(storageKey(userId));
    if (!raw) return null;
    const at = (JSON.parse(raw) as Snapshot)?.at;
    return typeof at === 'number' ? Date.now() - at : null;
  } catch {
    return null;
  }
}

/**
 * Call at the top of useSystemData, BEFORE the useQuery calls: hydration runs
 * synchronously during the first render for a user so the queries mount with
 * data already present.
 */
export function useWarmStart(): void {
  const { userId } = useAuth();
  const queryClient = useQueryClient();
  const hydratedFor = useRef<string | null>(null);

  if (userId && hydratedFor.current !== userId) {
    hydratedFor.current = userId;
    hydrateWarmStart(queryClient, userId);
  }

  useEffect(() => {
    if (!userId) return;

    // One-shot refresh for hydrated STATIC queries when the snapshot is old.
    // fetchStatus 'idle' guard: SEMI queries are already refetching on mount —
    // never duplicate an in-flight request.
    const age = snapshotAge(userId);
    const refresh =
      age !== null && age > FRESH_MS
        ? setTimeout(() => {
            void queryClient.invalidateQueries({
              predicate: (q) =>
                WARM_KEYS.some((k) => JSON.stringify(k) === JSON.stringify(q.queryKey)) &&
                q.state.fetchStatus === 'idle',
            });
          }, 500)
        : null;

    // Persist on cache writes (debounced) + on tab close.
    let writeTimer: ReturnType<typeof setTimeout> | null = null;
    const scheduleWrite = () => {
      if (writeTimer) clearTimeout(writeTimer);
      writeTimer = setTimeout(() => persistWarmSnapshot(queryClient, userId), WRITE_DEBOUNCE_MS);
    };
    const unsubscribe = queryClient.getQueryCache().subscribe(scheduleWrite);
    const onHide = () => persistWarmSnapshot(queryClient, userId);
    window.addEventListener('pagehide', onHide);

    return () => {
      if (refresh) clearTimeout(refresh);
      if (writeTimer) clearTimeout(writeTimer);
      unsubscribe();
      window.removeEventListener('pagehide', onHide);
    };
  }, [userId, queryClient]);
}
