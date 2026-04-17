/**
 * Per-user agent pipeline: trigger a run for the current user.
 * Called when the user loads the app (if agents are enabled in their settings).
 */

import { authedFetch } from './auth';

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
  thesis_ready?: boolean;
  active_thesis_version_id?: string | null;
  thesis_error?: string | null;
}

/** Live state of the per-user persistent background loop. */
export interface LoopStatus {
  loop_alive: boolean;
  agents_enabled: boolean;
  agents_status: 'running' | 'stopped' | 'error';
  agents_last_started_at: string | null;
}

export async function fetchAgentsStatus(): Promise<AgentsStatus | null> {
  try {
    const res = await authedFetch(`${API_BASE}/api/agents/status`, { headers: { Accept: 'application/json' } });
    if (!res.ok) return null;
    return (await res.json()) as AgentsStatus;
  } catch {
    return null;
  }
}

export async function fetchLoopStatus(): Promise<LoopStatus | null> {
  try {
    const res = await authedFetch(`${API_BASE}/api/agents/loop-status`, {
      headers: { Accept: 'application/json' },
    });
    if (!res.ok) return null;
    return (await res.json()) as LoopStatus;
  } catch {
    return null;
  }
}

/**
 * Enable or disable the persistent background agent loop.
 * enabled=true  → starts loop (does not override individual agent toggles)
 * enabled=false → disables all agents + stops loop
 */
export async function toggleAgents(enabled: boolean): Promise<{ ok: boolean }> {
  try {
    const res = await authedFetch(`${API_BASE}/api/agents/toggle`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
      body: JSON.stringify({ enabled }),
    });
    if (!res.ok) return { ok: false };
    return (await res.json()) as { ok: boolean };
  } catch {
    return { ok: false };
  }
}

export async function triggerAgents(): Promise<TriggerResult> {
  const res = await authedFetch(`${API_BASE}/api/agents/trigger`, {
    method: 'POST',
    headers: { Accept: 'application/json' },
  });
  const data = (await res.json()) as TriggerResult;
  return data;
}
