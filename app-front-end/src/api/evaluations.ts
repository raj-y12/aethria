import { apiRequest, encodedId } from './client';

export interface EvaluationRun {
  evaluation_id: string;
  evidence_snapshot_hash: string;
  thesis_version_id?: string | null;
  policy_version_id: string;
  policy_hash: string;
  rubric_version: string;
  partner_rules_version: string;
  partner_rules_hash: string;
  model_manifest: Record<string, unknown>;
  prompt_manifest: Record<string, unknown>;
  status: string;
  created_at?: string;
}

export interface CriterionAssessment {
  criterion_assessment_id: string;
  criterion: string;
  score?: number | null;
  confidence: number;
  evidence_sufficiency: string;
  reasoning: string;
  missing_evidence: string[];
}

export interface RecommendationRecord {
  recommendation_id: string;
  recommended_state: 'advance' | 'monitor' | 'pass' | 'insufficient_evidence';
  attention_priority: number;
  confidence: number;
  decision_drivers: string[];
  principal_risks: string[];
  mandate_conflicts: string[];
  missing_information: string[];
  change_conditions: string[];
  human_review_required: boolean;
  change_explanation?: string | null;
}

export interface EvaluationRecord {
  evaluation: EvaluationRun;
  criteria: CriterionAssessment[];
  recommendation: RecommendationRecord | null;
}

export function fetchCurrentEvaluation(opportunityId: string): Promise<EvaluationRecord> {
  return apiRequest(`/api/opportunities/${encodedId(opportunityId, 'opportunityId')}/evaluation`);
}

export function evaluateOpportunity(opportunityId: string): Promise<EvaluationRecord> {
  return apiRequest(`/api/opportunities/${encodedId(opportunityId, 'opportunityId')}/evaluate`, { method: 'POST' });
}
