import { apiRequest, encodedId } from './client';

export type IdentityStatus = 'unresolved' | 'resolved' | 'needs_review' | 'rejected';
export type IdentityCaseStatus = 'open' | 'resolved' | 'deferred' | 'rejected';

export interface Company {
  company_id: string;
  canonical_name: string;
  canonical_domain: string;
  identity_confidence: number;
  status: string;
  created_at: string;
  updated_at: string;
}

export interface Opportunity {
  opportunity_id: string;
  company_id: string;
  context_key: string;
  decision_state: string;
  service_level: number;
  first_observation_id?: string | null;
  latest_observation_id?: string | null;
  legacy_startup_id?: string | null;
  current_evaluation_id?: string | null;
  current_recommendation_id?: string | null;
  current_ruling_id?: string | null;
  current_ruling_decision?: string | null;
  created_at: string;
  updated_at: string;
}

export interface OpportunityDecisionView extends Opportunity {
  canonical_name: string;
  canonical_domain?: string | null;
  workflow_state?: string;
  workflow_version?: number;
  recommended_state?: string | null;
  recommendation_confidence?: number | null;
  attention_priority?: number | null;
  recommendation_id?: string | null;
  evaluation_id?: string | null;
  evidence_snapshot_hash?: string | null;
  thesis_version_id?: string | null;
  policy_version_id?: string | null;
  decision_drivers?: string[];
  principal_risks?: string[];
  missing_information?: string[];
  change_conditions?: string[];
  current_ruling_rationale?: string | null;
  current_ruling_created_at?: string | null;
  ruling_history?: CanonicalRulingRecord[];
}

export type CanonicalRulingDecision = 'advance' | 'monitor' | 'pass' | 'invest';

export interface CanonicalRulingRecord {
  ruling_id: string;
  recommendation_id?: string | null;
  decision: CanonicalRulingDecision | string;
  rationale?: string | null;
  risk_acknowledgement?: string | null;
  mandate_exception?: string | null;
  investor_confidence?: number | null;
  actor_id?: string | null;
  prior_ruling_id?: string | null;
  created_at?: string | null;
}

export interface SourceObservation {
  observation_id: string;
  channel: string;
  observed_name: string;
  observed_domain?: string | null;
  external_event_key?: string | null;
  lookup_id?: string | null;
  legacy_startup_id?: string | null;
  company_id?: string | null;
  identity_status: IdentityStatus | string;
  identity_confidence: number;
  observed_at: string;
  created_at: string;
  updated_at: string;
}

export interface IdentityCandidate {
  company_id: string;
  canonical_name: string;
  canonical_domain: string;
  confidence: number;
  evidence_urls: string[];
  reason: string;
}

export interface IdentityResolutionCase {
  identity_case_id: string;
  observation_id: string;
  status: IdentityCaseStatus | string;
  reason_code: string;
  candidates: IdentityCandidate[];
  selected_company_id?: string | null;
  resolution_note?: string | null;
  resolved_by?: string | null;
  resolved_at?: string | null;
  created_at: string;
  updated_at: string;
}

export interface IdentityAdmission {
  observation_id: string;
  status: string;
  company_id?: string | null;
  opportunity_id?: string | null;
  identity_case_id?: string | null;
  confidence?: number | null;
  blocks_evaluation: boolean;
  created: boolean;
}

export interface IdentityCaseGroup {
  group_key: string;
  canonical_domain: string | null;
  observation_count: number;
  observed_names: string[];
  sources: string[];
  cases: IdentityResolutionCase[];
}

export type IdentityResolutionInput =
  | { action: 'match'; selected_company_id: string; resolution_note?: string }
  | { action: 'create'; canonical_name: string; canonical_domain: string; resolution_note?: string }
  | { action: 'defer' | 'reject'; resolution_note?: string };

export function fetchCompany(companyId: string): Promise<Company> {
  return apiRequest(`/api/companies/${encodedId(companyId, 'companyId')}`);
}

export function fetchOpportunity(opportunityId: string): Promise<Opportunity> {
  return apiRequest(`/api/opportunities/${encodedId(opportunityId, 'opportunityId')}`);
}

export async function fetchOpportunities(limit = 100): Promise<OpportunityDecisionView[]> {
  const result = await apiRequest<{ opportunities?: OpportunityDecisionView[] }>(`/api/opportunities?limit=${limit}`);
  return Array.isArray(result.opportunities) ? result.opportunities : [];
}

export function fetchOpportunityDecisionView(opportunityId: string): Promise<OpportunityDecisionView> {
  return apiRequest(`/api/opportunities/${encodedId(opportunityId, 'opportunityId')}/decision-view`);
}

export function fetchOpportunityByLegacyStartup(startupId: string): Promise<Opportunity | null> {
  return apiRequest<Opportunity>(`/api/startups/${encodedId(startupId, 'startupId')}/opportunity`)
    .catch((error: unknown) => {
      if (error && typeof error === 'object' && 'status' in error && error.status === 404) return null;
      throw error;
    });
}

export async function fetchObservations(
  status?: IdentityStatus,
  limit = 100,
): Promise<SourceObservation[]> {
  const params = new URLSearchParams({ limit: String(limit) });
  if (status) params.set('status', status);
  const result = await apiRequest<{ observations?: SourceObservation[] }>(`/api/observations?${params}`);
  return Array.isArray(result.observations) ? result.observations : [];
}

export async function fetchIdentityCases(
  status: IdentityCaseStatus = 'open',
  limit = 100,
): Promise<IdentityResolutionCase[]> {
  const params = new URLSearchParams({ status, limit: String(limit) });
  const result = await apiRequest<{ cases?: IdentityResolutionCase[] }>(`/api/identity-cases?${params}`);
  return Array.isArray(result.cases) ? result.cases : [];
}

export function resolveIdentityCase(
  identityCaseId: string,
  input: IdentityResolutionInput,
): Promise<IdentityAdmission | IdentityResolutionCase> {
  return apiRequest(`/api/identity-cases/${encodedId(identityCaseId, 'identityCaseId')}/resolve`, {
    method: 'POST',
    body: JSON.stringify(input),
  });
}

export async function fetchIdentityCaseGroups(
  status: IdentityCaseStatus = 'open',
  limit = 100,
): Promise<IdentityCaseGroup[]> {
  const params = new URLSearchParams({ status, limit: String(limit) });
  const result = await apiRequest<{ groups?: IdentityCaseGroup[] }>(`/api/identity-cases/groups?${params}`);
  return Array.isArray(result.groups) ? result.groups : [];
}

export function resolveIdentityCaseGroup(
  groupKey: string,
  input: IdentityResolutionInput,
): Promise<{ group_key: string; results: unknown[] }> {
  return apiRequest(`/api/identity-cases/groups/${encodedId(groupKey, 'groupKey')}/resolve`, {
    method: 'POST',
    body: JSON.stringify(input),
  });
}
