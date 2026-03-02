/**
 * Settings API. Control plane only. No auto-save; explicit PATCH.
 */

const API_BASE = typeof window !== 'undefined' ? '' : 'http://localhost:8000';

export interface CostBudget {
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

export interface Settings {
  cost_budget: CostBudget;
  agent_config: AgentConfig;
  portfolio: Portfolio;
}

export interface ValidationError {
  message: string;
  errors: string[];
}

export async function fetchSettings(): Promise<Settings> {
  const res = await fetch(`${API_BASE}/api/settings`, {
    headers: { Accept: 'application/json' },
  });
  if (!res.ok) throw new Error(`Settings API error: ${res.status}`);
  return res.json();
}

export async function patchSettings(
  body: Partial<Settings>
): Promise<{ data?: Settings; error?: ValidationError }> {
  const res = await fetch(`${API_BASE}/api/settings`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
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
