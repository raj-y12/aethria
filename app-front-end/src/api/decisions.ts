import { apiRequest, encodedId } from './client';

/** User-facing opportunity dispositions. Investment is a later portfolio event. */
export type HumanRulingDecision = 'advance' | 'monitor' | 'pass';
/** Legacy value retained so historical rulings can still be rendered. */
export type LegacyHumanRulingDecision = 'invest';
export type HumanRulingRecordDecision = HumanRulingDecision | LegacyHumanRulingDecision;
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

export interface InvestmentTransitionInput {
  rationale: string;
  investor_confidence?: number;
}

export interface InvestmentTransitionRecord {
  decision: 'invest';
  idempotent?: boolean;
  position?: Record<string, unknown> | null;
  ruling_id?: string;
  opportunity_id?: string;
}

export interface HumanRuling extends Omit<HumanRulingInput, 'decision'> {
  ruling_id: string;
  decision: HumanRulingRecordDecision;
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

/** Record the post-diligence portfolio transition; not an initial opportunity ruling. */
export function createInvestmentTransition(
  opportunityId: string,
  input: InvestmentTransitionInput,
): Promise<InvestmentTransitionRecord> {
  return apiRequest(`/api/opportunities/${encodedId(opportunityId, 'opportunityId')}/investment`, {
    method: 'POST', body: JSON.stringify(input),
  });
}

export async function listHumanRulings(opportunityId: string, limit = 50): Promise<HumanRuling[]> {
  const result = await apiRequest<{ rulings?: HumanRuling[] }>(
    `/api/opportunities/${encodedId(opportunityId, 'opportunityId')}/rulings?limit=${limit}`,
  );
  return Array.isArray(result.rulings) ? result.rulings : [];
}
