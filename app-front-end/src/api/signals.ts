import type { SignalItem } from '../types/startup';

const API_BASE = typeof window !== 'undefined' ? '' : 'http://localhost:8000';

export async function fetchSignals(): Promise<SignalItem[]> {
  const res = await fetch(`${API_BASE}/api/signals`, {
    headers: { Accept: 'application/json' },
  });
  if (!res.ok) return [];
  const data = await res.json();
  return Array.isArray(data) ? data : [];
}
