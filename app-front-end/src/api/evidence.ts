import { apiRequest, encodedId } from './client';

export type EvidenceVerificationState = 'unverified' | 'verified' | 'disputed' | 'revoked';
export type ClaimAssertionClass =
  | 'externally_verified'
  | 'founder_asserted'
  | 'operator_asserted'
  | 'model_inferred'
  | 'conflicted'
  | 'unverified';

export interface EvidenceArtifact {
  artifact_id: string;
  opportunity_id?: string | null;
  artifact_type: string;
  source_uri?: string | null;
  title?: string | null;
  trust_class: string;
  access_class: string;
  retention_policy?: string;
  published_at?: string | null;
  effective_at?: string | null;
  retrieved_at?: string;
  created_at?: string;
}

export interface EvidenceItem {
  evidence_item_id: string;
  artifact_id: string;
  item_type: string;
  display_excerpt: string;
  source_locator?: string | null;
  effective_at?: string | null;
  expires_at?: string | null;
  verification_state: EvidenceVerificationState;
  source_quality: number;
  extraction_confidence: number;
}

export interface Claim {
  claim_id: string;
  company_id: string;
  opportunity_id?: string | null;
  claim_type: string;
  display_text: string;
  assertion_class: ClaimAssertionClass;
  confidence: number;
  material: boolean;
  status: string;
  period?: string | null;
  operator_attribution?: string | null;
  created_at?: string;
  updated_at?: string;
}

export interface ClaimEvidenceLink {
  link_id: string;
  claim_id: string;
  evidence_item_id: string;
  relationship: string;
  support_strength: number;
  rationale: string;
}

export interface EvidencePlan {
  evidence_plan_id: string;
  opportunity_id: string;
  trigger_type: string;
  status: string;
  missing_evidence: string[];
  search_questions: string[];
  max_artifacts: number;
  budget_usd: number;
  created_at: string;
}

export interface EvidenceLedger {
  artifacts: EvidenceArtifact[];
  items?: EvidenceItem[];
  evidence_items?: EvidenceItem[];
  claims: Claim[];
  links: ClaimEvidenceLink[];
  plans: EvidencePlan[];
}

interface EvidenceLedgerResponse {
  artifacts: EvidenceArtifact[];
  evidence_items?: EvidenceItem[];
  claims: Claim[];
  claim_evidence_links?: ClaimEvidenceLink[];
  evidence_plans?: EvidencePlan[];
}

export interface EvidencePlanInput {
  trigger_type: string;
  missing_evidence: string[];
  search_questions: string[];
  max_artifacts?: number;
  budget_usd?: number;
}

export type ClaimCorrectionInput = {
  action: 'withdraw' | 'contradict' | 'mark_stale' | 'supersede';
  rationale: string;
};

export async function fetchEvidenceLedger(opportunityId: string): Promise<EvidenceLedger> {
  const response = await apiRequest<EvidenceLedgerResponse>(
    `/api/opportunities/${encodedId(opportunityId, 'opportunityId')}/evidence?view=${import.meta.env.DEV ? 'full' : 'analyst'}`,
  );
  return {
    artifacts: response.artifacts ?? [],
    evidence_items: response.evidence_items ?? [],
    claims: response.claims ?? [],
    links: response.claim_evidence_links ?? [],
    plans: response.evidence_plans ?? [],
  };
}

export function createEvidencePlan(opportunityId: string, input: EvidencePlanInput): Promise<EvidencePlan> {
  return apiRequest(`/api/opportunities/${encodedId(opportunityId, 'opportunityId')}/evidence-plans`, {
    method: 'POST', body: JSON.stringify(input),
  });
}

export function correctClaim(claimId: string, input: ClaimCorrectionInput): Promise<{ claim_id: string; status: string; updated_at?: string }> {
  return apiRequest(`/api/claims/${encodedId(claimId, 'claimId')}/correct`, {
    method: 'POST', body: JSON.stringify(input),
  });
}
