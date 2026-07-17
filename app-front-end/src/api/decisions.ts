import { apiRequest, encodedId } from './client';

export type HumanRulingDecision = 'advance' | 'monitor' | 'pass' | 'invest';
export type OverrideType =
  | 'evidence_correction' | 'missing_private_evidence' | 'policy_disagreement'
  | 'founder_judgment' | 'market_judgment' | 'timing' | 'strategic_exception'
  | 'relationship_context' | 'confidence_disagreement';

export interface HumanRulingInput {
  recommendation_id?: string;
  decision: HumanRulingDecision;
  rationale: string;
  risk_acknowledgement?: string;
  mandate_exception?: string;
  investor_confidence?: number;
  override_type?: OverrideType;
  override_note?: string;
}

export interface HumanRuling extends HumanRulingInput {
  ruling_id: string;
  opportunity_id?: string;
  prior_ruling_id?: string | null;
  actor_id?: string;
  created_at?: string;
}

export function createHumanRuling(opportunityId: string, input: HumanRulingInput): Promise<HumanRuling> {
  return apiRequest(`/api/opportunities/${encodedId(opportunityId, 'opportunityId')}/rulings`, {
    method: 'POST', body: JSON.stringify(input),
  });
}

export async function listHumanRulings(opportunityId: string, limit = 50): Promise<HumanRuling[]> {
  const result = await apiRequest<{ rulings?: HumanRuling[] }>(
    `/api/opportunities/${encodedId(opportunityId, 'opportunityId')}/rulings?limit=${limit}`,
  );
  return Array.isArray(result.rulings) ? result.rulings : [];
}
