import { authedFetch } from './auth';

const API_BASE =
  typeof window !== 'undefined'
    ? (import.meta.env.VITE_API_URL ?? '')
    : 'http://localhost:8000';

export interface ActivitySummary {
  found: number;
  reviewed: number;
  decided: number;
  escalations: number;
}

export async function fetchActivitySummary(): Promise<ActivitySummary> {
  const res = await authedFetch(`${API_BASE}/api/activity/summary`);
  if (!res.ok) throw new Error('activity summary request failed');
  return res.json() as Promise<ActivitySummary>;
}
