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

export function deriveOverridePatterns(): Promise<Record<string, unknown>> {
  return apiRequest('/api/fund-intelligence/derive-overrides', { method: 'POST' });
}

export async function fetchPolicyProposals(status?: PolicyProposalStatus, limit = 100): Promise<PolicyProposal[]> {
  const params = new URLSearchParams({ limit: String(limit) });
  if (status) params.set('status', status);
  const result = await apiRequest<{ proposals?: PolicyProposal[] }>(`/api/fund-intelligence/proposals?${params}`);
  return Array.isArray(result.proposals) ? result.proposals : [];
}

export function fetchPolicyProposal(proposalId: string): Promise<PolicyProposal> {
  return apiRequest(`/api/fund-intelligence/proposals/${encodedId(proposalId, 'proposalId')}`);
}

export function previewPolicyProposal(proposalId: string): Promise<Record<string, unknown>> {
  return apiRequest(`/api/fund-intelligence/proposals/${encodedId(proposalId, 'proposalId')}/preview`, { method: 'POST' });
}

export function reviewPolicyProposal(
  proposalId: string,
  input: { action: ProposalReviewAction; rationale: string; edited_policy_patch?: Record<string, unknown> },
): Promise<Record<string, unknown>> {
  return apiRequest(`/api/fund-intelligence/proposals/${encodedId(proposalId, 'proposalId')}/review`, {
    method: 'POST', body: JSON.stringify(input),
  });
}

export function publishGovernedPolicy(
  policyVersionId: string,
  fundConfig: Record<string, unknown>,
): Promise<Record<string, unknown>> {
  return apiRequest(`/api/fund-intelligence/policy-versions/${encodedId(policyVersionId, 'policyVersionId')}/publish`, {
    method: 'POST', body: JSON.stringify({ fund_config: fundConfig }),
  });
}

