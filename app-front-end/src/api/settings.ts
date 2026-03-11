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

export interface SystemHealth {
  calibration_warning?: string | null;
  verdict_distribution?: Record<string, number>;
}

export interface Settings {
  cost_budget: CostBudget;
  agent_config: AgentConfig;
  portfolio: Portfolio;
  meta_agent?: MetaAgentSettings;
  system_health?: SystemHealth;
  budget_status?: Record<string, { calls_used: number; calls_limit: number; tokens_used: number; tokens_limit: number }>;
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
