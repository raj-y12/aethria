/**
 * Per-user agent pipeline: trigger a run for the current user.
 * Called when the user loads the app (if agents are enabled in their settings).
 */

import { getAuthHeaders } from './auth';

const API_BASE =
  typeof window !== 'undefined'
    ? (import.meta.env.VITE_API_URL ?? '')
    : 'http://localhost:8000';

export type TriggerStatus = 'queued' | 'skipped' | 'unavailable';

export interface TriggerResult {
  status: TriggerStatus | string;
  reason?: string;
  user_id?: string;
}

export interface AgentsStatus {
  worker_ready: boolean;
  supabase_configured: boolean;
  openai_configured: boolean;
  agents_will_run: boolean;
}

export async function fetchAgentsStatus(): Promise<AgentsStatus | null> {
  const headers = { Accept: 'application/json', ...(await getAuthHeaders()) };
  try {
    const res = await fetch(`${API_BASE}/api/agents/status`, { headers });
    if (!res.ok) return null;
    return (await res.json()) as AgentsStatus;
  } catch {
    return null;
  }
}

export async function triggerAgents(): Promise<TriggerResult> {
  const headers = { Accept: 'application/json', ...(await getAuthHeaders()) };
  const res = await fetch(`${API_BASE}/api/agents/trigger`, {
    method: 'POST',
    headers,
  });
  const data = (await res.json()) as TriggerResult;
  return data;
}
