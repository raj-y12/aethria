/**
 * Settings API. Control plane only. No auto-save; explicit PATCH.
 */

import { authedFetch } from './auth';
import type { FundConfiguration } from '../lib/fundConfiguration';

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
  scout_grounded_citations_enabled?: boolean;
  scout_fail_closed_on_empty_retrieval?: boolean;
  scout_retrieval_provider?: 'tavily' | 'serpapi' | string;
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

export interface UserPreferences {
  layoutPreferences: Record<string, unknown>;
  savedFilters: Array<Record<string, unknown>>;
  displayPreferences: Record<string, unknown>;
  personalOverrides: Record<string, unknown>;
}

export interface FundMemory {
  historical_decisions: Array<Record<string, unknown>>;
  recurring_risk_patterns: Array<Record<string, unknown>>;
  calibration_observations: Array<Record<string, unknown>>;
  precedent_references: Array<Record<string, unknown>>;
  mandate_drift_notes: Array<Record<string, unknown>>;
}

export interface FundIdentity {
  fund_name: string;
  stage_focus: string;
  geographic_focus: string;
  /** Official site URL or domain; used to filter wrong-TLD links in Scout references. */
  canonical_website?: string;
}

export interface Settings {
  fund_config?: FundConfiguration;
  user_preferences?: UserPreferences;
  fund_memory?: FundMemory;
  fund_identity?: FundIdentity;
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

export interface PolicyPreviewResponse {
  policy?: {
    policy_version_id: string;
    policy_hash: string;
    generated_at?: string;
    published_at?: string;
    warnings?: string[];
    dimensions?: Record<string, unknown>;
  };
  warnings?: string[];
  error?: ValidationError;
}

export async function fetchSettings(): Promise<Settings> {
  const r = await authedFetch(`${API_BASE}/api/settings`, {
    headers: { Accept: 'application/json' },
  });
  if (!r.ok) throw new Error(`Settings API error: ${r.status}`);
  return r.json() as Promise<Settings>;
}

export async function patchSettings(
  body: Partial<Settings>
): Promise<{ data?: Settings; error?: ValidationError }> {
  const res = await authedFetch(`${API_BASE}/api/settings`, {
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

export async function previewPolicy(
  fundConfig: FundConfiguration
): Promise<PolicyPreviewResponse> {
  const res = await authedFetch(`${API_BASE}/api/settings/policy/preview`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
    body: JSON.stringify({ fund_config: fundConfig }),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    return {
      error: {
        message: data?.detail?.message ?? 'Policy preview failed',
        errors: data?.detail?.errors ?? [],
      },
    };
  }
  return data as PolicyPreviewResponse;
}

export async function publishPolicy(
  fundConfig: FundConfiguration
): Promise<PolicyPreviewResponse> {
  const res = await authedFetch(`${API_BASE}/api/settings/policy/publish`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
    body: JSON.stringify({ fund_config: fundConfig }),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    return {
      error: {
        message: data?.detail?.message ?? 'Policy publish failed',
        errors: data?.detail?.errors ?? [],
      },
    };
  }
  return data as PolicyPreviewResponse;
}
