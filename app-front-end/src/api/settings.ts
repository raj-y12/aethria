/**
 * Settings API. Control plane only. No auto-save; explicit PATCH.
 */

import { getAuthHeaders } from './auth';

const API_BASE =
  typeof window !== 'undefined'
    ? (import.meta.env.VITE_API_URL ?? '')
    : 'http://localhost:8000';

export interface CostBudget {
  enabled: boolean;
  max_tokens_per_run: number;
  daily_cost_ceiling: number;
  weekly_cost_ceiling: number;
  cooldown_seconds: number;
}

export interface AgentConfig {
  scouts_enabled: boolean;
  reviewers_enabled: boolean;
  partners_enabled: boolean;
  max_agents_per_run: number;
  confidence_threshold: number | string;
  // Scout-specific config
  scout_region: string; // "europe" | "global"
  scout_serp_enabled: boolean;
  scout_serp_daily_budget: number;
}

export interface Portfolio {
  auto_watchlist: boolean;
  signal_scan_frequency: string;
  memo_verbosity: string;
}

export interface MetaAgentSettings {
  enabled: boolean;
  interval_seconds: number;
  min_reviews: number;
  min_decisions: number;
  mutation_cooldown_cycles: number;
}

export interface AgentBudgetStatus {
  agent_id: string;
  daily_calls_used: number;
  daily_calls_limit: number;
  daily_tokens_used: number;
  daily_tokens_limit: number;
  in_cooldown: boolean;
  cooldown_until: string | null;
}

export interface SystemHealth {
  calibration_warning: string | null;
  pending_escalations: number;
  queue_depths: {
    unreviewed: number;
    undecided: number;
    watchlist: number;
  };
  budget_status: AgentBudgetStatus[];
}

export interface Settings {
  cost_budget: CostBudget;
  agent_config: AgentConfig;
  portfolio: Portfolio;
  meta_agent?: MetaAgentSettings;
  system_health?: SystemHealth;
}

export interface ValidationError {
  message: string;
  errors: string[];
}

export async function fetchSettings(): Promise<Settings> {
  const auth = await getAuthHeaders();
  const headers = { Accept: 'application/json', ...auth };
  const [settings, systemHealth] = await Promise.all([
    fetch(`${API_BASE}/api/settings`, { headers }).then((r) => {
      if (!r.ok) throw new Error(`Settings API error: ${r.status}`);
      return r.json();
    }),
    fetch(`${API_BASE}/api/analytics/system-health`, { headers }).then((r) =>
      r.ok ? r.json() : Promise.reject(new Error(`System health API error: ${r.status}`))
    ),
  ]);
  return { ...(settings as Settings), system_health: systemHealth as SystemHealth };
}

export async function patchSettings(
  body: Partial<Settings>
): Promise<{ data?: Settings; error?: ValidationError }> {
  const headers = { 'Content-Type': 'application/json', Accept: 'application/json', ...(await getAuthHeaders()) };
  const res = await fetch(`${API_BASE}/api/settings`, {
    method: 'PATCH',
    headers,
    body: JSON.stringify(body),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    return {
      error: {
        message: data?.detail?.message ?? 'Validation failed',
        errors: data?.detail?.errors ?? [],
      },
    };
  }
  return { data: data as Settings };
}
