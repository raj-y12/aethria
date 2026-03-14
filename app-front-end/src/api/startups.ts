import type { Startup } from '../types/startup';
import { getAuthHeaders } from './auth';

const API_BASE =
  typeof window !== 'undefined'
    ? (import.meta.env.VITE_API_URL ?? '')
    : 'http://localhost:8000';

export async function fetchStartups(): Promise<Startup[]> {
  const headers = { Accept: 'application/json', ...(await getAuthHeaders()) };
  const res = await fetch(`${API_BASE}/api/startups`, { headers });
  if (!res.ok) throw new Error(`Startups API error: ${res.status}`);
  const data = await res.json();
  return Array.isArray(data) ? data : [];
}

export async function fetchMemo(startupId: string): Promise<string | null> {
  const headers = { Accept: 'application/json', ...(await getAuthHeaders()) };
  const res = await fetch(`${API_BASE}/api/startups/${encodeURIComponent(startupId)}/memo`, { headers });
  if (!res.ok) return null;
  const data = await res.json();
  return typeof data?.memo === 'string' ? data.memo : null;
}
