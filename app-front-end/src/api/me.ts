import { authedFetch } from './auth';

const API_BASE =
  typeof window !== 'undefined'
    ? (import.meta.env.VITE_API_URL ?? '')
    : 'http://localhost:8000';

export interface MeResponse {
  user_id: string;
}

export async function fetchMe(): Promise<MeResponse | null> {
  const res = await authedFetch(`${API_BASE}/api/me`, { headers: { Accept: 'application/json' } });
  if (!res.ok) return null;
  const data = await res.json();
  return typeof data?.user_id === 'string' ? { user_id: data.user_id } : null;
}
