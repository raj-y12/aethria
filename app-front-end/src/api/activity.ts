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

export async function markActivitySeen(): Promise<void> {
  await authedFetch(`${API_BASE}/api/activity/seen`, { method: 'POST' });
}

/**
 * After password sign-in, the global Clerk token getter may not be wired yet.
 * Call with the session token from Clerk so the welcome screen can load activity.
 */
export async function fetchActivitySummaryWithToken(token: string): Promise<ActivitySummary | null> {
  const t = token.trim();
  if (!t) return null;
  const res = await fetch(`${API_BASE}/api/activity/summary`, {
    headers: { Accept: 'application/json', Authorization: `Bearer ${t}` },
  });
  if (!res.ok) return null;
  return (await res.json()) as ActivitySummary;
}
