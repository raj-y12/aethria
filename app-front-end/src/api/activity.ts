import { authedFetch } from './auth';

const API_BASE =
  typeof window !== 'undefined'
    ? (import.meta.env.VITE_API_URL ?? '')
    : 'http://localhost:8000';

export interface ActivitySummary {
  found: number;
  reviewed: number;
  /** Backwards-compatible alias for agent_decided. */
  decided: number;
  agent_decided?: number;
  human_reviewed?: number;
  open_in_progress?: number;
  escalations: number;
}

export async function fetchActivitySummary(): Promise<ActivitySummary> {
  const res = await authedFetch(`${API_BASE}/api/activity/summary`);
  if (!res.ok) throw new Error('activity summary request failed');
  return res.json() as Promise<ActivitySummary>;
}

export async function markActivitySeen(options: { keepalive?: boolean } = {}): Promise<void> {
  const res = await authedFetch(`${API_BASE}/api/activity/seen`, {
    method: 'POST',
    keepalive: options.keepalive,
  });
  if (!res.ok) throw new Error('activity seen marker request failed');
}

/**
 * After password sign-in, the global Clerk token getter may not be wired yet.
 * Call with the session token from Clerk so the welcome screen can load activity.
 *
 * Time-boxed: the welcome screen's CTA waits on this call, so a slow or
 * cold backend must degrade to "no stats" after `timeoutMs`, never hang.
 */
export async function fetchActivitySummaryWithToken(
  token: string,
  timeoutMs = 8_000,
): Promise<ActivitySummary | null> {
  const t = token.trim();
  if (!t) return null;
  try {
    const res = await fetch(`${API_BASE}/api/activity/summary`, {
      headers: { Accept: 'application/json', Authorization: `Bearer ${t}` },
      signal: AbortSignal.timeout(timeoutMs),
    });
    if (!res.ok) return null;
    return (await res.json()) as ActivitySummary;
  } catch {
    return null; // timeout or network error — welcome screen proceeds without stats
  }
}

/** Mark the end of the login report before the global token getter is wired. */
export async function markActivitySeenWithToken(token: string): Promise<void> {
  const t = token.trim();
  if (!t) return;
  const res = await fetch(`${API_BASE}/api/activity/seen`, {
    method: 'POST',
    headers: { Accept: 'application/json', Authorization: `Bearer ${t}` },
    keepalive: true,
  });
  if (!res.ok) throw new Error('activity seen marker request failed');
}

/**
 * Fire-and-forget backend wake-up: hit the public /health endpoint so a cold
 * or sleeping instance starts warming while the user is still typing their
 * credentials. One cheap unauthenticated GET per login-page visit.
 */
export function pingBackendWarmup(): void {
  void fetch(`${API_BASE}/health`, { signal: AbortSignal.timeout(30_000) }).catch(() => undefined);
}
