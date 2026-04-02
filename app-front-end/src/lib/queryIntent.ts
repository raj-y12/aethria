/**
 * Query intent: explicit cache + refresh policy for expensive backend (Supabase-backed API).
 * No implicit polling — intervals only when intent + live gate allow it.
 */

export type QueryIntent = 'STATIC' | 'SEMI_DYNAMIC' | 'LIVE';

/** Tab visible + recent user activity (see useQueryLiveGate). */
export type QueryLiveGate = {
  tabVisible: boolean;
  userActive: boolean;
};

export type GetQueryConfigOptions = {
  liveGate?: QueryLiveGate;
  /**
   * SEMI_DYNAMIC / LIVE: desired poll interval (ms).
   * SEMI_DYNAMIC is clamped to 120_000 max. LIVE is clamped to 5_000–15_000.
   */
  pollIntervalMs?: number;
  /** LIVE only: caller enables short-interval polling (e.g. active search UI). */
  liveIntentEnabled?: boolean;
};

const SEMI_STALE_MS = 90_000;
const SEMI_POLL_MAX_MS = 120_000;
const LIVE_STALE_MS = 8_000;
const LIVE_POLL_MIN_MS = 5_000;
const LIVE_POLL_MAX_MS = 15_000;

/** Subset of TanStack Query options we set from intent (explicit types for useQuery inference). */
export interface IntentQueryOptions {
  staleTime: number;
  /** Only `false` or a positive interval (ms) — never `true`. */
  refetchInterval: number | false;
  refetchOnWindowFocus: boolean;
  refetchOnMount: boolean;
  refetchOnReconnect: boolean;
}

function semiPollInterval(gateOk: boolean, pollIntervalMs: number): number | false {
  if (!gateOk || pollIntervalMs <= 0) return false;
  return Math.min(pollIntervalMs, SEMI_POLL_MAX_MS);
}

/**
 * TanStack Query options derived from intent. Merge into useQuery({ ... }).
 */
export function getQueryConfig(intent: QueryIntent, options: GetQueryConfigOptions = {}): IntentQueryOptions {
  const { liveGate, pollIntervalMs = 60_000, liveIntentEnabled = false } = options;
  const gateOk = Boolean(liveGate?.tabVisible && liveGate?.userActive);

  switch (intent) {
    case 'STATIC':
      return {
        staleTime: Number.POSITIVE_INFINITY,
        refetchInterval: false,
        refetchOnWindowFocus: false,
        refetchOnMount: false,
        refetchOnReconnect: false,
      };
    case 'SEMI_DYNAMIC':
      return {
        staleTime: SEMI_STALE_MS,
        refetchInterval: semiPollInterval(gateOk, pollIntervalMs),
        refetchOnWindowFocus: false,
        refetchOnMount: true,
        refetchOnReconnect: false,
      };
    case 'LIVE': {
      const liveOn = Boolean(liveIntentEnabled && gateOk);
      const clamped = Math.min(
        Math.max(pollIntervalMs || LIVE_POLL_MIN_MS, LIVE_POLL_MIN_MS),
        LIVE_POLL_MAX_MS
      );
      return {
        staleTime: liveOn ? LIVE_STALE_MS : Number.POSITIVE_INFINITY,
        refetchInterval: liveOn ? clamped : false,
        refetchOnWindowFocus: false,
        refetchOnMount: true,
        refetchOnReconnect: false,
      };
    }
  }
}

/** User considered inactive after this many ms without input. */
export const QUERY_LIVE_IDLE_MS = 45_000;
