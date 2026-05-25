import { authedFetch } from './auth';

const API_BASE =
  typeof window !== 'undefined' ? (import.meta.env.VITE_API_URL ?? '') : 'http://localhost:8000';

export interface FundThesisVersionRow {
  id: string;
  version_number: number;
  is_active: boolean;
  created_at: string;
}

export interface FundThesisSummary {
  thesis_id: string;
  active_version_id: string;
  active_version_number: number;
  parsed_json: Record<string, unknown>;
  raw_text: string;
  mode: 'rule_based' | 'embedding';
  embedding: {
    model?: string;
    dimension: number;
    dimensions?: number;
    status: string;
    created_at?: string;
  };
  versions: FundThesisVersionRow[];
  recent_pipeline_links: Array<{
    id: string;
    thesis_version_id: string;
    pipeline_run_id: string | null;
    affected_startups_count: number;
    created_at: string;
  }>;
}

export interface FundThesisRuntime {
  /** Core runtime contract from GET /api/fund-thesis/runtime */
  thesis_version_id?: string;
  mode?: 'rule_based' | 'embedding' | 'missing';
  embedding_status?: 'pending' | 'ready';
  embedding_model?: string;
  has_embeddings?: boolean;
  /** Extended fields when thesis is loaded (System panel) */
  thesis_ready?: boolean;
  error?: string;
  detail?: string;
  active_version_id?: string;
  active_version_number?: number;
  fund_thesis_updated_at?: string;
  thesis_mode?: 'rule_based' | 'embedding';
  embedding?: {
    status: string;
    model: string;
    dimension: number;
  };
  embedding_dimensions?: number;
  alignment_stats?: {
    reviewed_with_thesis_count: number;
    pct_matching_thesis: number | null;
    avg_alignment_score: number | null;
    drift_vs_previous: number | null;
  };
  version_timeline?: FundThesisVersionRow[];
  parsed_json?: Record<string, unknown>;
}

export async function fetchFundThesisSummary(): Promise<FundThesisSummary | null> {
  const res = await authedFetch(`${API_BASE}/api/fund-thesis`, { headers: { Accept: 'application/json' } });
  if (res.status === 404) return null;
  if (!res.ok) throw new Error(await res.text());
  return (await res.json()) as FundThesisSummary;
}

export async function fetchFundThesisRuntime(): Promise<FundThesisRuntime> {
  const res = await authedFetch(`${API_BASE}/api/fund-thesis/runtime`, { headers: { Accept: 'application/json' } });
  if (!res.ok) throw new Error(await res.text());
  return (await res.json()) as FundThesisRuntime;
}

export async function postFundThesisVersion(
  rawText: string,
  options?: { skip_embedding?: boolean; parsed_json?: Record<string, unknown> },
): Promise<{ status: string; version_id: string; version_number: number }> {
  const body: Record<string, unknown> = { raw_text: rawText };
  if (options?.skip_embedding === true) body.skip_embedding = true;
  if (options?.parsed_json != null) body.parsed_json = options.parsed_json;
  const res = await authedFetch(`${API_BASE}/api/fund-thesis/versions`, {
    method: 'POST',
    headers: { Accept: 'application/json', 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(await res.text());
  const data = (await res.json()) as { status?: string; version_id: string; version_number: number };
  return {
    status: data.status ?? 'created',
    version_id: data.version_id,
    version_number: data.version_number,
  };
}

export async function patchFundThesisActiveVersion(versionId: string): Promise<void> {
  const res = await authedFetch(`${API_BASE}/api/fund-thesis/active`, {
    method: 'PATCH',
    headers: { Accept: 'application/json', 'Content-Type': 'application/json' },
    body: JSON.stringify({ version_id: versionId }),
  });
  if (!res.ok) throw new Error(await res.text());
}

export type FundThesisReprocessDryRunResult = {
  dry_run: true;
  eligible: number;
};

export type FundThesisReprocessRunResult = {
  processed: number;
  skipped: number;
  failed: number;
};

export async function postFundThesisReprocessMissing(options?: {
  dryRun?: boolean;
}): Promise<FundThesisReprocessDryRunResult | FundThesisReprocessRunResult> {
  const q = options?.dryRun === true ? '?dry_run=true' : '';
  const res = await authedFetch(`${API_BASE}/api/fund-thesis/reprocess-missing${q}`, {
    method: 'POST',
    headers: { Accept: 'application/json' },
  });
  if (!res.ok) throw new Error(await res.text());
  return (await res.json()) as FundThesisReprocessDryRunResult | FundThesisReprocessRunResult;
}
