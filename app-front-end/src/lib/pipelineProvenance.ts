import type { EvaluationRecord } from '../api/evaluations';
import type { EvidenceLedger } from '../api/evidence';
import type { Startup } from '../types/startup';
import type { MemoDecisionBrief } from './memoDecisionBrief';
import { canonicalCriteriaToStructuredScoring } from './canonicalScoring';
import { getVisibleRecommendation } from './queueAttentionDriver';

/** Audit only: this report observes the existing projections; it never selects
 * the score or recommendation consumed by product components. Unknown history
 * stays unknown, even when a legacy value happens to equal a canonical one. */
export function buildPipelineProvenance({
  startup, evaluation, evidence, brief, scorecardEnabled,
}: {
  startup: Startup;
  evaluation?: EvaluationRecord | null;
  evidence?: EvidenceLedger;
  brief: MemoDecisionBrief;
  scorecardEnabled: boolean;
}) {
  const scoring = canonicalCriteriaToStructuredScoring(evaluation);
  const recommendation = evaluation?.recommendation;
  const dimensions = ['market', 'product', 'technical', 'execution', 'defensibility'] as const;
  const legacyOverall = startup.projection_provenance?.legacy_scores.overall_score ?? startup.review?.overall_score ?? startup.review?.aggregate_score ?? null;
  const record = (value: unknown): Record<string, unknown> =>
    value && typeof value === 'object' && !Array.isArray(value) ? value as Record<string, unknown> : {};
  const scoutTrace = record(startup.agent_trace?.scout);
  const reviewerTrace = record(startup.agent_trace?.reviewer);
  const partnerTrace = record(startup.agent_trace?.partner);
  const partnerProvenance = startup.projection_provenance?.partner_provenance ?? record(partnerTrace.provenance);
  const partnerEvaluationId = partnerProvenance.evaluation_run_id ?? null;
  const currentEvaluationId = evaluation?.evaluation.evaluation_id ?? null;
  const startupOpportunityId = startup.canonical_opportunity_id ?? null;
  const evaluationOpportunityId = evaluation?.provenance?.opportunity_id ?? null;
  const opportunityId = evaluationOpportunityId ?? startupOpportunityId;
  return {
    lineage: {
      pipeline_run_id: evaluation?.provenance?.pipeline_run_id ?? null,
      scout_run_id: evaluation?.provenance?.scout_run_id ?? scoutTrace.scout_run_id ?? null,
      reviewer_run_id: reviewerTrace.reviewer_run_id ?? null,
      reviewer_pipeline_run_id: reviewerTrace.pipeline_run_id ?? null,
      partner_run_id: partnerTrace.partner_run_id ?? null,
      partner_evaluation_run_id: partnerEvaluationId,
      current_evaluation_run_id: currentEvaluationId,
      partner_uses_current_evaluation: partnerEvaluationId && currentEvaluationId
        ? partnerEvaluationId === currentEvaluationId : null,
    },
    startup_id: startup.id,
    opportunity_id: opportunityId ?? null,
    opportunity_id_sources: {
      evaluation: evaluationOpportunityId,
      startup_projection: startupOpportunityId,
      resolved_from: evaluationOpportunityId ? 'evaluation_provenance' : startupOpportunityId ? 'startup_projection' : null,
      mismatch: Boolean(evaluationOpportunityId && startupOpportunityId && evaluationOpportunityId !== startupOpportunityId),
    },
    data_sources: {
      startup: startup.frontend_projection?.source ?? 'Legacy startup API or fixture; exact request unavailable',
      memo_partial: 'May be merged by mergeMemoPartial',
      canonical: '/api/opportunities/{opportunityId}/evaluation via useMemoDecisionBrief',
      evidence: '/api/opportunities/{opportunityId}/evidence via useMemoDecisionBrief',
      queue_score: 'Unavailable: getQueueConvictionPct returns null',
      memo_score: 'canonicalCriteriaToStructuredScoring; no legacy fallback',
      memo_recommendation: 'buildMemoDecisionBrief: evidence block, then ruling status, then canonical lean',
      thesis_alignment: 'startup.review.thesis_alignment_score (values <= 1 multiplied by 10)',
    },
    memo: {
      score_origin: scoring ? 'COMPATIBILITY_PROJECTION' : null,
      scorecard_enabled: scorecardEnabled,
      overall_score: scorecardEnabled && recommendation?.recommended_state !== 'insufficient_evidence'
        ? scoring?.overall_score ?? null : null,
      calculated_overall_score: scoring?.overall_score ?? null,
      overall_calculation: 'Mean of scored market/product/technical/execution; excludes defensibility',
      overall_confidence: scoring?.overall_confidence ?? null,
      confidence_calculation: 'Mean of non-null confidence for scored driver dimensions',
      status: brief.status,
      system_lean: brief.lean,
      canonical_recommendation: recommendation ?? null,
      human_ruling: brief.ruling,
      evidence_coverage: brief.coverage,
      dimensions: dimensions.map((key) => {
        const criterion = evaluation?.criteria.find((item) => item.criterion === key);
        const legacyScore = startup.projection_provenance?.legacy_scores[`${key}_score`] ?? startup.review?.[`${key}_score`] ?? null;
        return {
          dimension: key,
          score: criterion?.score ?? null,
          score_origin: criterion ? evaluation?.provenance?.criteria?.find((item) => item.criterion === key)?.score_origin ?? 'CANONICAL_EVALUATION' : null,
          criterion: criterion ?? null,
          legacy_score: legacyScore,
          legacy_score_source: startup.review?.score_source ?? 'UNKNOWN_LEGACY',
          differs_from_legacy: criterion?.score != null && legacyScore != null
            ? criterion.score !== legacyScore : null,
        };
      }),
    },
    compatibility: {
      visible_queue_recommendation: getVisibleRecommendation(startup),
      queue_recommendation_source: startup.human_resolution?.decision
        ? 'HUMAN_OVERRIDE' : startup.partner ? 'startup.partner.recommendation' : null,
      partner: startup.partner ?? null,
      frontend_projection: startup.frontend_projection ?? null,
      stored_projection: startup.projection_provenance ?? null,
      legacy_overall_score: legacyOverall,
      legacy_score_source: startup.review?.score_source ?? 'UNKNOWN_LEGACY',
      legacy_score_breakdown: startup.review?.score_breakdown ?? null,
      overall_differs_from_canonical_projection: scoring && legacyOverall != null
        ? scoring.overall_score !== legacyOverall : null,
      thesis_alignment_score: startup.review?.thesis_alignment_score ?? null,
    },
    evaluation_provenance: evaluation?.provenance ?? null,
    evaluation_manifest: evaluation?.evaluation ?? null,
    // This is the current ledger, not a claim that it reconstructs the historical snapshot.
    current_evidence_ledger: evidence ?? null,
    agent_trace: startup.agent_trace ?? null,
  };
}
