import type {
  MetaCycleReport,
  ScoutWeights,
  CalibrationState,
  MetaPromptState,
  MetaEvalSet,
  PromptEvaluateResult,
  MetaInsightsPayload,
} from '../types/startup';
import { authedFetch } from './auth';

const API_BASE =
  typeof window !== 'undefined'
    ? (import.meta.env.VITE_API_URL ?? '')
    : 'http://localhost:8000';

export async function fetchMetaReports(): Promise<MetaCycleReport[]> {
  const res = await authedFetch(`${API_BASE}/api/meta/reports`, { headers: { Accept: 'application/json' } });
  if (!res.ok) return [];
  const data = await res.json();
  return Array.isArray(data) ? data : [];
}

export async function fetchMetaInsights(): Promise<MetaInsightsPayload> {
  const res = await authedFetch(`${API_BASE}/api/meta/insights`, { headers: { Accept: 'application/json' } });
  if (!res.ok) throw new Error(`Meta insights failed: ${res.status}`);
  return res.json() as Promise<MetaInsightsPayload>;
}

export async function fetchScoutWeights(): Promise<ScoutWeights> {
  const res = await authedFetch(`${API_BASE}/api/meta/weights`, { headers: { Accept: 'application/json' } });
  if (!res.ok) return { MarketDrivenScout: 0.25, BuilderTechnicalScout: 0.25, PainPointScout: 0.25, ContrarianScout: 0.25 };
  return res.json();
}

export async function fetchCalibrationState(): Promise<CalibrationState> {
  const res = await authedFetch(`${API_BASE}/api/meta/calibration`, { headers: { Accept: 'application/json' } });
  if (!res.ok) return { confidence_threshold_override: null, reviewer_weak_threshold_override: null, reviewer_strong_threshold_override: null, last_calibrated_at: null, last_calibrated_cycle: 0, calibration_history: [] };
  return res.json();
}

export async function triggerMetaCycle(): Promise<{ status: string; cycle_number: number }> {
  const res = await authedFetch(`${API_BASE}/api/meta/trigger`, {
    method: 'POST',
    headers: { Accept: 'application/json' },
  });
  if (!res.ok) throw new Error(`Trigger failed: ${res.status}`);
  return res.json();
}

export async function fetchMetaPromptState(includePrompt?: string): Promise<MetaPromptState> {
  const q = includePrompt ? `?include_prompt=${encodeURIComponent(includePrompt)}` : '';
  const res = await authedFetch(`${API_BASE}/api/meta/prompt-state${q}`, { headers: { Accept: 'application/json' } });
  if (!res.ok) {
    return { active: {}, active_detail: {}, pending: [] };
  }
  return res.json();
}

export async function promoteMetaPrompt(agentTarget: string, libraryKey: string): Promise<{ ok: boolean; active?: Record<string, string> }> {
  const res = await authedFetch(`${API_BASE}/api/meta/prompts/promote`, {
    method: 'POST',
    headers: { Accept: 'application/json', 'Content-Type': 'application/json' },
    body: JSON.stringify({ agent_target: agentTarget, library_key: libraryKey }),
  });
  if (!res.ok) {
    const err = await res.text();
    throw new Error(err || `Promote failed: ${res.status}`);
  }
  return res.json();
}

export async function resetMetaPrompt(agentTarget: string): Promise<{ ok: boolean; active?: Record<string, string> }> {
  const res = await authedFetch(`${API_BASE}/api/meta/prompts/reset`, {
    method: 'POST',
    headers: { Accept: 'application/json', 'Content-Type': 'application/json' },
    body: JSON.stringify({ agent_target: agentTarget }),
  });
  if (!res.ok) {
    const err = await res.text();
    throw new Error(err || `Reset failed: ${res.status}`);
  }
  return res.json();
}

export async function fetchMetaEvalSet(): Promise<MetaEvalSet> {
  const res = await authedFetch(`${API_BASE}/api/meta/eval-set`, { headers: { Accept: 'application/json' } });
  if (!res.ok) return { startup_ids: [], count: 0, max: 50 };
  return res.json();
}

export async function saveMetaEvalSet(startupIds: string[]): Promise<MetaEvalSet & { ok?: boolean; missing_startup_ids?: string[] }> {
  const res = await authedFetch(`${API_BASE}/api/meta/eval-set`, {
    method: 'PUT',
    headers: { Accept: 'application/json', 'Content-Type': 'application/json' },
    body: JSON.stringify({ startup_ids: startupIds }),
  });
  if (!res.ok) {
    const err = await res.text();
    throw new Error(err || `Save eval set failed: ${res.status}`);
  }
  return res.json();
}

export async function runPromptEvaluation(
  agentTarget: string,
  libraryKey: string,
  startupIds?: string[],
): Promise<PromptEvaluateResult> {
  const res = await authedFetch(`${API_BASE}/api/meta/prompts/evaluate`, {
    method: 'POST',
    headers: { Accept: 'application/json', 'Content-Type': 'application/json' },
    body: JSON.stringify({
      agent_target: agentTarget,
      library_key: libraryKey,
      ...(startupIds?.length ? { startup_ids: startupIds } : {}),
    }),
  });
  const data = await res.json();
  if (!res.ok) {
    const d = data as { detail?: string };
    throw new Error(d.detail || JSON.stringify(data) || `Evaluate failed: ${res.status}`);
  }
  return data as PromptEvaluateResult;
}
