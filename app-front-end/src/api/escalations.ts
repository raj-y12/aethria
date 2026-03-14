import type { EscalationItem } from '../types/startup';
import { getAuthHeaders } from './auth';

const API_BASE = typeof window !== 'undefined' ? '' : 'http://localhost:8000';

export async function fetchEscalations(): Promise<EscalationItem[]> {
  const headers = { Accept: 'application/json', ...(await getAuthHeaders()) };
  const res = await fetch(`${API_BASE}/api/escalations`, { headers });
  if (!res.ok) return [];
  const data = await res.json();
  return Array.isArray(data) ? data : [];
}

export async function resolveEscalation(
  startupId: string,
  decision: 'YES' | 'NO' | 'MAYBE',
  notes: string
): Promise<{ status: string }> {
  const headers = { 'Content-Type': 'application/json', Accept: 'application/json', ...(await getAuthHeaders()) };
  const res = await fetch(`${API_BASE}/api/escalations/${encodeURIComponent(startupId)}/resolve`, {
    method: 'POST',
    headers,
    body: JSON.stringify({ decision, notes }),
  });
  if (!res.ok) throw new Error(`Resolve failed: ${res.status}`);
  return res.json();
}
