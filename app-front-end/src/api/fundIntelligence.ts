import { apiRequest, encodedId } from './client';

export type PolicyProposalStatus = 'draft' | 'ready_for_review' | 'accepted' | 'edited_and_accepted' | 'rejected' | 'deferred' | 'expired';
export type ProposalReviewAction = 'accept' | 'edit_and_accept' | 'reject' | 'defer';

export interface PolicyProposal {
  policy_proposal_id: string;
  proposal_fingerprint: string;
  pattern_summary: string;
  attribution: string;
  sample_size: number;
  confidence: number;
  limitations: string[];
  proposed_policy_patch: Record<string, unknown>;
  status: PolicyProposalStatus;
  reviewer_rationale?: string | null;
  resulting_policy_version_id?: string | null;
  created_at: string;
  updated_at: string;
}

export interface GovernedPolicyVersion {
  governed_policy_version_id: string;
  policy_proposal_id: string;
  policy_patch: Record<string, unknown>;
  policy_hash: string;
  status: 'draft' | 'published' | 'superseded';
  published_policy_id?: string | null;
  published_policy_hash?: string | null;
}

export interface PolicyProposalDetail {
  proposal: PolicyProposal;
  signals: Array<Record<string, unknown>>;
  impact_previews: Array<Record<string, unknown>>;
  policy_versions: GovernedPolicyVersion[];
}

export interface PolicyReviewResult {
  proposal: PolicyProposal;
  policy_version: GovernedPolicyVersion | null;
  production_policy_changed: false;
}

export type FundSufficiency = 'insufficient' | 'emerging' | 'moderate' | 'strong' | string;

export interface InterpretationProvenance {
  case_id: string;
  ruling_id: string;
  interpretation_id: string;
  version: number;
  source?: string | null;
  created_at?: string | null;
  provenance?: Record<string, unknown>;
}

export interface FundObservation {
  observation_id: string;
  observation_type: string;
  observation_family?: string;
  segment: Record<string, string>;
  supporting_case_ids: string[];
  contradictory_case_ids: string[];
  sample_size: number;
  time_window: { from: string | null; to: string | null };
  thesis_versions: string[];
  mandate_versions: string[];
  policy_versions: string[];
  metric: Record<string, unknown>;
  sufficiency: FundSufficiency;
  descriptive_confidence: number;
  limitations: string[];
  direction?: string;
  involved_criteria?: string[];
  involved_factors?: string[];
  value_ranges?: Record<string, string>;
  interpretation_as_of: 'latest_retrospective' | 'none_available' | string;
  interpretation_provenance: InterpretationProvenance[];
}

export interface FundHypothesis {
  hypothesis_id: string;
  hypothesis_family: string;
  statement: string;
  source_observation_ids: string[];
  source_observation_types: string[];
  segment: Record<string, string>;
  supporting_case_ids: string[];
  contradictory_case_ids: string[];
  sample_size: number;
  sufficiency: FundSufficiency;
  descriptive_confidence: number;
  mandate_versions: string[];
  thesis_versions: string[];
  policy_versions: string[];
  time_window: { from: string | null; to: string | null };
  limitations: string[];
  status: string;
}

export interface FundReplayPreview {
  hypothesis_id: string;
  hypothesis_family: string;
  affected_segment: Record<string, string>;
  replay_status: 'not_replayable' | string;
  historical_cases_evaluated: string[];
  cases_changed: string[];
  cases_unchanged: string[];
  cases_indeterminate: string[];
  original_recommendations: string[];
  simulated_recommendations: string[];
  mandate_versions: string[];
  policy_versions: string[];
  time_window: { from: string | null; to: string | null };
  limitations: string[];
  outcome_context_used_for_replay: false;
}

export interface CounterfactualProposal {
  proposal_id: string;
  source_hypothesis_id: string;
  source_hypothesis_family: string;
  proposal_status: 'draft_counterfactual' | 'insufficient_basis' | string;
  replay_compatibility: 'machine_rule_complete' | 'not_ready' | string;
  supporting_case_ids: string[];
  contradictory_case_ids: string[];
  limitations: string[];
}

function intelligenceQuery(params: Record<string, string | undefined>): string {
  const query = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value) query.set(key, value);
  }
  const encoded = query.toString();
  return encoded ? `?${encoded}` : '';
}

export async function fetchFundObservations(options: Record<string, string | undefined> = {}): Promise<FundObservation[]> {
  const result = await apiRequest<{ observations?: FundObservation[] }>(
    `/api/fund-intelligence/observations${intelligenceQuery(options)}`,
  );
  return Array.isArray(result.observations) ? result.observations : [];
}

export async function fetchFundHypotheses(options: Record<string, string | undefined> = {}): Promise<FundHypothesis[]> {
  const result = await apiRequest<{ hypotheses?: FundHypothesis[] }>(
    `/api/fund-intelligence/hypotheses${intelligenceQuery(options)}`,
  );
  return Array.isArray(result.hypotheses) ? result.hypotheses : [];
}

export function fetchFundReplayPreview(hypothesisId: string): Promise<FundReplayPreview> {
  return apiRequest(`/api/fund-intelligence/hypotheses/${encodedId(hypothesisId, 'hypothesisId')}/replay`);
}

export async function fetchCounterfactualProposals(options: Record<string, string | undefined> = {}): Promise<CounterfactualProposal[]> {
  const result = await apiRequest<{ counterfactual_proposals?: CounterfactualProposal[] }>(
    `/api/fund-intelligence/counterfactual-proposals${intelligenceQuery(options)}`,
  );
  return Array.isArray(result.counterfactual_proposals) ? result.counterfactual_proposals : [];
}

export function deriveOverridePatterns(): Promise<Record<string, unknown>> {
  return apiRequest('/api/fund-intelligence/derive-overrides', { method: 'POST' });
}

export async function fetchPolicyProposals(status?: PolicyProposalStatus, limit = 100): Promise<PolicyProposal[]> {
  const params = new URLSearchParams({ limit: String(limit) });
  if (status) params.set('status', status);
  const result = await apiRequest<{ proposals?: PolicyProposal[] }>(`/api/fund-intelligence/proposals?${params}`);
  return Array.isArray(result.proposals) ? result.proposals : [];
}

export function fetchPolicyProposal(proposalId: string): Promise<PolicyProposalDetail> {
  return apiRequest(`/api/fund-intelligence/proposals/${encodedId(proposalId, 'proposalId')}`);
}

export function previewPolicyProposal(
  proposalId: string,
  input: { action: Extract<ProposalReviewAction, 'accept' | 'edit_and_accept'>; edited_policy_patch?: Record<string, unknown> },
): Promise<Record<string, unknown>> {
  return apiRequest(`/api/fund-intelligence/proposals/${encodedId(proposalId, 'proposalId')}/preview`, {
    method: 'POST', body: JSON.stringify(input),
  });
}

export function reviewPolicyProposal(
  proposalId: string,
  input: { action: ProposalReviewAction; rationale: string; edited_policy_patch?: Record<string, unknown> },
): Promise<PolicyReviewResult> {
  return apiRequest(`/api/fund-intelligence/proposals/${encodedId(proposalId, 'proposalId')}/review`, {
    method: 'POST', body: JSON.stringify(input),
  });
}

export function publishGovernedPolicy(
  policyVersionId: string,
): Promise<Record<string, unknown>> {
  return apiRequest(`/api/fund-intelligence/policy-versions/${encodedId(policyVersionId, 'policyVersionId')}/publish`, {
    method: 'POST',
  });
}
