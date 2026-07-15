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
  import_batch_id: string;
  status: string;
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

export function importCsv(input: CsvImportInput): Promise<ImportResult> {
  return apiRequest('/api/imports/csv', { method: 'POST', body: JSON.stringify(input) });
}

export function fetchImport(importBatchId: string): Promise<ImportResult> {
  return apiRequest(`/api/imports/${encodedId(importBatchId, 'importBatchId')}`);
}

export function createOutcome(companyId: string, input: OutcomeInput): Promise<OutcomeRecord> {
  return apiRequest(`/api/companies/${encodedId(companyId, 'companyId')}/outcomes`, {
    method: 'POST', body: JSON.stringify(input),
  });
}

export function fetchOutcomes(companyId: string, limit = 100): Promise<OutcomeRecord[]> {
  return apiRequest(`/api/companies/${encodedId(companyId, 'companyId')}/outcomes?limit=${limit}`);
}

export function fetchOutcomeCoverage(): Promise<Record<string, unknown>> {
  return apiRequest('/api/outcomes/coverage');
}

export interface ConfidentialArtifactInput {
  artifact_type: 'pitch_deck' | 'email';
  content_hash: string;
  storage_reference: string;
  title?: string;
  source_uri?: string;
  retention_policy: string;
  published_at?: string;
  effective_at?: string;
}

export function registerConfidentialArtifact(
  opportunityId: string,
  input: ConfidentialArtifactInput,
): Promise<Record<string, unknown>> {
  return apiRequest(`/api/opportunities/${encodedId(opportunityId, 'opportunityId')}/confidential-artifacts`, {
    method: 'POST', body: JSON.stringify(input),
  });
}

