import type { EscalationItem } from '../types/startup';
import { authedFetch } from './auth';

const API_BASE =
  typeof window !== 'undefined'
    ? (import.meta.env.VITE_API_URL ?? '')
    : 'http://localhost:8000';

export async function fetchEscalations(): Promise<EscalationItem[]> {
  const res = await authedFetch(`${API_BASE}/api/escalations`, { headers: { Accept: 'application/json' } });
  if (!res.ok) return [];
  const data = await res.json();
  return Array.isArray(data) ? data : [];
}

export async function resolveEscalation(
  startupId: string,
  decision: 'YES' | 'NO' | 'MAYBE',
  notes: string
): Promise<{ status: string }> {
  const res = await authedFetch(`${API_BASE}/api/escalations/${encodeURIComponent(startupId)}/resolve`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
    body: JSON.stringify({ decision, notes }),
  });
  if (!res.ok) throw new Error(`Resolve failed: ${res.status}`);
  return res.json();
}
