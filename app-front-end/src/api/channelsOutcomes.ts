import { apiRequest, encodedId } from './client';

export type ImportSource = 'csv' | 'crm_csv' | 'event_csv' | 'referral_csv';

export interface CsvImportInput {
  source?: ImportSource;
  idempotency_key: string;
  csv_text: string;
  name_field?: string;
  domain_field?: string | null;
  external_id_field?: string | null;
  verify_domains?: boolean;
}

export interface ImportResult {
  batch?: {
    import_batch_id: string;
    status: string;
    row_count?: number;
    resolved_count?: number;
    review_count?: number;
    error_count?: number;
    [key: string]: unknown;
  };
  rows?: Array<Record<string, unknown>>;
  idempotent_replay?: boolean;
  // Retained for compatibility with early in-memory adapters.
  import_batch_id?: string;
  status?: string;
  [key: string]: unknown;
}

export type OutcomeType = 'financing' | 'revenue_milestone' | 'customer_milestone' | 'product_launch' | 'acquisition' | 'shutdown' | 'leadership_change' | 'follow_on_decision' | 'other';
export type OutcomeValence = 'positive' | 'negative' | 'neutral' | 'mixed';

export interface OutcomeInput {
  opportunity_id?: string;
  outcome_type: OutcomeType;
  valence: OutcomeValence;
  summary: string;
  verification_state?: 'unverified' | 'verified' | 'disputed';
  materiality: number;
  effective_at?: string;
  evidence_artifact_ids?: string[];
  supersedes_outcome_id?: string;
}

export interface OutcomeRecord extends OutcomeInput {
  outcome_observation_id: string;
  company_id: string;
  observed_at: string;
  created_at: string;
}

export interface OutcomeInterpretation {
  causal_inference_supported: false;
  [key: string]: unknown;
}

export interface OutcomeResult {
  outcome: OutcomeRecord;
  interpretation: OutcomeInterpretation;
}

export interface OutcomeCoverage {
  eligible_opportunity_count?: number;
  observed_opportunity_count?: number;
  coverage_ratio?: number;
  outcomes_by_valence?: Record<string, number>;
  causal_inference_supported?: false;
  limitations?: string[];
  // Compatibility with the pre-canonical analytics adapter.
  total_companies?: number;
  companies_with_outcomes?: number;
  coverage_rate?: number;
  verified_outcomes?: number;
}

export function importCsv(input: CsvImportInput): Promise<ImportResult> {
  return apiRequest('/api/imports/csv', { method: 'POST', body: JSON.stringify(input) });
}

export function fetchImport(importBatchId: string): Promise<ImportResult> {
  return apiRequest(`/api/imports/${encodedId(importBatchId, 'importBatchId')}`);
}

export function createOutcome(companyId: string, input: OutcomeInput): Promise<OutcomeResult> {
  return apiRequest(`/api/companies/${encodedId(companyId, 'companyId')}/outcomes`, {
    method: 'POST', body: JSON.stringify(input),
  });
}

export async function fetchOutcomes(companyId: string, limit = 100): Promise<OutcomeResult[]> {
  const result = await apiRequest<{ outcomes?: OutcomeResult[] }>(
    `/api/companies/${encodedId(companyId, 'companyId')}/outcomes?limit=${limit}`,
  );
  return Array.isArray(result.outcomes) ? result.outcomes : [];
}

export function fetchOutcomeCoverage(): Promise<OutcomeCoverage> {
  return apiRequest('/api/outcomes/coverage');
}
