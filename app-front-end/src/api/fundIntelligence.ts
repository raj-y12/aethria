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
  resultingFundConfig: Record<string, unknown>,
): Promise<Record<string, unknown>> {
  return apiRequest(`/api/fund-intelligence/proposals/${encodedId(proposalId, 'proposalId')}/preview`, {
    method: 'POST', body: JSON.stringify({ resulting_fund_config: resultingFundConfig }),
  });
}

export function reviewPolicyProposal(
  proposalId: string,
  input: { action: ProposalReviewAction; rationale: string; resulting_fund_config?: Record<string, unknown> },
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
