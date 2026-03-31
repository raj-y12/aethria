import type { Startup } from '../types/startup';
import { authedFetch } from './auth';

const API_BASE =
  typeof window !== 'undefined'
    ? (import.meta.env.VITE_API_URL ?? '')
    : 'http://localhost:8000';

export async function fetchStartups(): Promise<Startup[]> {
  const res = await authedFetch(`${API_BASE}/api/startups`, { headers: { Accept: 'application/json' } });
  if (!res.ok) throw new Error(`Startups API error: ${res.status}`);
  const data = await res.json();
  return Array.isArray(data) ? data : [];
}

export async function fetchMemo(startupId: string): Promise<string | null> {
  const res = await authedFetch(`${API_BASE}/api/startups/${encodeURIComponent(startupId)}/memo`, {
    headers: { Accept: 'application/json' },
  });
  if (!res.ok) return null;
  const data = await res.json();
  return typeof data?.memo === 'string' ? data.memo : null;
}

export async function queueOnDemandLookup(
  lookupInput: string
): Promise<{ status: string; companyName: string; lookupInputType?: string }> {
  const input = lookupInput.trim();
  if (!input) {
    throw new Error('Lookup input is required');
  }
  const res = await authedFetch(`${API_BASE}/api/startups/lookup`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Accept: 'application/json',
    },
    body: JSON.stringify({
      lookup_input: input,
    }),
  });
  if (!res.ok) {
    throw new Error(`Lookup API error: ${res.status}`);
  }
  const data = await res.json();
  return {
    status: typeof data?.status === 'string' ? data.status : 'queued',
    companyName: typeof data?.company_name === 'string' ? data.company_name : input,
    lookupInputType: typeof data?.lookup_input_type === 'string' ? data.lookup_input_type : undefined,
  };
}
