import { apiRequest, encodedId } from './client';

export type RecommendationState = 'advance' | 'monitor' | 'pass' | 'insufficient_evidence';

export interface EvaluationRun {
  evaluation_id: string;
  evidence_snapshot_hash?: string;
  thesis_version_id?: string | null;
  policy_version_id?: string;
  policy_hash?: string;
  rubric_version?: string;
  partner_rules_version?: string;
  partner_rules_hash?: string;
  model_manifest?: Record<string, unknown>;
  prompt_manifest?: Record<string, unknown>;
  status: string;
  created_at?: string;
}

/** Internal audit data. Analyst components select only investment explanations. */
export interface AssessmentValidation {
  reviewer_assessment_id?: string | null;
  proposed_score?: number | null;
  validated_score?: number | null;
  score_status: 'NOT_VALIDATED' | 'VALIDATED' | 'CAPPED' | 'BLOCKED' | 'UNKNOWN' | 'CURRENT_EVALUATION';
  cap_reason?: string | null;
  contradiction_status?: 'PRESENT' | 'NONE_RECORDED' | 'UNKNOWN';
}

export interface CriterionAssessment {
  criterion_assessment_id: string;
  criterion: string;
  score?: number | null;
  confidence: number;
  evidence_sufficiency: string;
  reasoning: string;
  supporting_claim_ids: string[];
  contradicting_claim_ids: string[];
  missing_evidence: string[];
  quality_flags: string[];
  deterministic_adjustments?: Record<string, unknown> & {
    assessment_validation?: AssessmentValidation;
    change_from_prior_review?: {
      previous_score: number | null;
      previous_reasoning: string;
      score_changed: boolean;
      reasoning_changed: boolean;
    };
  };
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

export type ScoreOrigin = 'CANONICAL_EVALUATION' | 'REVIEWER_ASSESSMENT' | 'VALIDATED_REVIEWER_ASSESSMENT' | 'REVIEWER_LEGACY' | 'PARTNER_LEGACY' | 'COMPATIBILITY_PROJECTION' | 'UNKNOWN_LEGACY';

/** Backend audit contract; unknown historical values remain null. */
export interface EvaluationProvenance {
  provenance_version: string;
  pipeline_run_id: string | null;
  pipeline_entry_type: string | null;
  company_id: string | null;
  opportunity_id: string | null;
  scout_run_id: string | null;
  source_scout_pipeline_run_id: string | null;
  evaluation_run_id: string | null;
  evidence_snapshot_hash: string | null;
  evidence_plan_id: string | null;
  evidence_artifact_ids: string[];
  claim_ids: string[];
  evidence_links: Record<string, unknown>[];
  score_origin: ScoreOrigin;
  score_schema_version: string | null;
  evaluation_rubric_version: string | null;
  reviewer_rules_version: string | null;
  partner_rules_version: string | null;
  thesis_version_id: string | null;
  policy_version: string | null;
  policy_hash: string | null;
  partner_rules_hash: string | null;
  recommendation_origin: string;
  canonical_recommendation: string | null;
  human_review_required: boolean | null;
  criteria: Array<{
    criterion: string;
    score_origin: ScoreOrigin;
    canonical_score: number | null;
    reviewer_proposed_score: number | null;
    legacy_score: number | null;
    support_status: string | null;
    supporting_claim_ids: string[];
    contradicting_claim_ids: string[];
    missing_evidence: string[];
    quality_flags: string[];
    validation: Record<string, unknown>;
  }>;
}

export interface EvaluationRecord {
  dependencies?: { state: 'current' | 'stale' | 'unknown'; reasons?: string[]; message: string };
  provenance?: Partial<EvaluationProvenance> | null;
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
      supporting_claim_ids: stringArray(criterion.supporting_claim_ids),
      contradicting_claim_ids: stringArray(criterion.contradicting_claim_ids),
      missing_evidence: stringArray(criterion.missing_evidence),
      quality_flags: stringArray(criterion.quality_flags),
      deterministic_adjustments: objectValue(criterion.deterministic_adjustments),
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
    `/api/opportunities/${encodedId(opportunityId, 'opportunityId')}/evaluation?view=${import.meta.env.DEV ? 'full' : 'analyst'}`,
  );
  return normalizeEvaluation(result);
}

export async function refreshEvaluation(
  opportunityId: string, scope: 'full' | 'partner' = 'full',
): Promise<EvaluationRecord> {
  const result = await apiRequest<EvaluationRecord>(
    `/api/opportunities/${encodedId(opportunityId, 'opportunityId')}/evaluate?scope=${scope}`,
    { method: 'POST' },
  );
  return normalizeEvaluation(result);
}
