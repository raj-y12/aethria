import type { SignalItem } from '../types/startup';
import { authedFetch } from './auth';

const API_BASE =
  typeof window !== 'undefined'
    ? (import.meta.env.VITE_API_URL ?? '')
    : 'http://localhost:8000';

export async function fetchSignals(): Promise<SignalItem[]> {
  const res = await authedFetch(`${API_BASE}/api/signals`, { headers: { Accept: 'application/json' } });
  if (!res.ok) return [];
  const data = await res.json();
  return Array.isArray(data) ? data : [];
}
