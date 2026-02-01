import type { Startup } from '../types/startup';

const API_BASE = typeof window !== 'undefined' ? '' : 'http://localhost:8000';

export async function fetchStartups(): Promise<Startup[]> {
  const res = await fetch(`${API_BASE}/api/startups`, {
    headers: { Accept: 'application/json' },
  });
  if (!res.ok) throw new Error(`Startups API error: ${res.status}`);
  const data = await res.json();
  return Array.isArray(data) ? data : [];
}

export async function fetchMemo(startupId: string): Promise<string | null> {
  const res = await fetch(`${API_BASE}/api/startups/${encodeURIComponent(startupId)}/memo`, {
    headers: { Accept: 'application/json' },
  });
  if (!res.ok) return null;
  const data = await res.json();
  return typeof data?.memo === 'string' ? data.memo : null;
}
