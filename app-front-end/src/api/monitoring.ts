import { apiRequest, encodedId } from './client';

export type RefreshReason =
  | 'new_observation' | 'missing_policy_evidence' | 'stale_decisive_evidence'
  | 'monitor_due' | 'verified_external_signal' | 'human_request' | 'policy_change'
  | 'claim_correction';

export interface RefreshEnvelope {
  max_search_queries?: number;
  max_artifacts?: number;
  max_model_tokens?: number;
  estimated_cost_usd?: number;
  providers?: string[];
  deadline_at?: string;
}

export interface RefreshAcceptance {
  status: string;
  job_id: string;
  pipeline_run_id: string;
  accepted_at: string;
  budget_reservation: Record<string, unknown>;
}

export interface MonitoringStatus {
  opportunity?: Record<string, unknown>;
  reservations?: Array<Record<string, unknown>>;
  [key: string]: unknown;
}

export function requestEvidenceRefresh(
  opportunityId: string,
  input: { reason: RefreshReason; request_key: string; envelope: RefreshEnvelope },
): Promise<RefreshAcceptance> {
  return apiRequest(`/api/opportunities/${encodedId(opportunityId, 'opportunityId')}/refresh`, {
    method: 'POST', body: JSON.stringify(input),
  });
}

export function setOpportunityServiceLevel(
  opportunityId: string,
  input: { service_level: number; lifecycle_reason: string; next_review_at?: string | null },
): Promise<Record<string, unknown>> {
  return apiRequest(`/api/opportunities/${encodedId(opportunityId, 'opportunityId')}/service-level`, {
    method: 'PATCH', body: JSON.stringify(input),
  });
}

export function fetchMonitoringStatus(opportunityId: string): Promise<MonitoringStatus> {
  return apiRequest(`/api/opportunities/${encodedId(opportunityId, 'opportunityId')}/monitoring`);
}

