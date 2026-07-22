import { apiRequest, encodedId } from './client';

export type RecommendationState = 'advance' | 'monitor' | 'pass' | 'insufficient_evidence';

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
  recommended_state: RecommendationState;
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

function parseJson(value: unknown, fallback: unknown): unknown {
  if (typeof value !== 'string') return value ?? fallback;
  try {
    return JSON.parse(value);
  } catch {
    return fallback;
  }
}

function stringArray(value: unknown): string[] {
  const parsed = parseJson(value, []);
  return Array.isArray(parsed) ? parsed.filter((item): item is string => typeof item === 'string') : [];
}

function objectValue(value: unknown): Record<string, unknown> {
  const parsed = parseJson(value, {});
  return parsed && typeof parsed === 'object' && !Array.isArray(parsed)
    ? parsed as Record<string, unknown>
    : {};
}

function normalizeEvaluation(result: EvaluationRecord): EvaluationRecord {
  const recommendation = result.recommendation;
  return {
    ...result,
    evaluation: {
      ...result.evaluation,
      model_manifest: objectValue(result.evaluation.model_manifest),
      prompt_manifest: objectValue(result.evaluation.prompt_manifest),
    },
    criteria: (result.criteria ?? []).map((criterion) => ({
      ...criterion,
      missing_evidence: stringArray(criterion.missing_evidence),
    })),
    recommendation: recommendation ? {
      ...recommendation,
      decision_drivers: stringArray(recommendation.decision_drivers),
      principal_risks: stringArray(recommendation.principal_risks),
      mandate_conflicts: stringArray(recommendation.mandate_conflicts),
      missing_information: stringArray(recommendation.missing_information),
      change_conditions: stringArray(recommendation.change_conditions),
    } : null,
  };
}

export async function fetchCurrentEvaluation(opportunityId: string): Promise<EvaluationRecord> {
  const result = await apiRequest<EvaluationRecord>(
    `/api/opportunities/${encodedId(opportunityId, 'opportunityId')}/evaluation`,
  );
  return normalizeEvaluation(result);
}
