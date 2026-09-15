import type { CriterionAssessment, EvaluationRecord } from '../api/evaluations';
import type { ScoringDimension, ScoringDimensionKey, StructuredScoring } from '../types/startup';

// Overall = mean of Market, Product, Technical, Execution — Defensibility is a
// moat signal, excluded from the mean. Matches AssessmentScorecard's own
// documented convention (METHOD_COPY, driverDims filter).
const DRIVER_KEYS: ScoringDimensionKey[] = ['market', 'product', 'technical', 'execution'];
const ALL_KEYS: ScoringDimensionKey[] = [...DRIVER_KEYS, 'defensibility'];

function dimensionFromCriterion(criterion: CriterionAssessment | undefined): ScoringDimension {
  const unscored = !criterion || criterion.score == null;
  return {
    score: unscored ? 0 : (criterion!.score as number),
    unscored,
    confidence: criterion?.confidence ?? null,
    // Canonical criteria carry one narrative reasoning string, not a per-component
    // breakdown — components stays empty and the scorecard already falls back to
    // `reasoning` when components is empty (AssessmentScorecard.tsx renderRow).
    components: {},
    reasoning: criterion?.reasoning ? [criterion.reasoning] : null,
    weaknesses: criterion?.quality_flags?.length
      ? criterion.quality_flags.map((flag) => flag.replace(/_/g, ' ')) : null,
  };
}

/** Adapts persisted authoritative criteria onto the StructuredScoring shape
 * AssessmentScorecard renders. Returns null when there's no canonical evaluation yet
 * Current criteria validate Reviewer proposals; historical criteria retain their
 * original evaluator semantics. Missing evaluations have no score fallback. */
export function canonicalCriteriaToStructuredScoring(
  evaluation: EvaluationRecord | null | undefined,
): StructuredScoring | null {
  if (!evaluation?.criteria?.length) return null;

  const byKey = new Map(evaluation.criteria.map((c) => [c.criterion, c]));
  const dims = Object.fromEntries(
    ALL_KEYS.map((key) => [key, dimensionFromCriterion(byKey.get(key))]),
  ) as Record<ScoringDimensionKey, ScoringDimension>;

  const scoredDrivers = DRIVER_KEYS.map((key) => dims[key]).filter((d) => !d.unscored);
  const overallScore = scoredDrivers.length
    ? scoredDrivers.reduce((sum, d) => sum + d.score, 0) / scoredDrivers.length
    : 0;
  const confidences = scoredDrivers
    .map((d) => d.confidence)
    .filter((c): c is number => c != null);
  const overallConfidence = confidences.length
    ? confidences.reduce((sum, c) => sum + c, 0) / confidences.length
    : null;

  return {
    policy_version_id: evaluation.evaluation.policy_version_id,
    policy_hash: evaluation.evaluation.policy_hash,
    market: dims.market,
    execution: dims.execution,
    product: dims.product,
    technical: dims.technical,
    defensibility: dims.defensibility,
    overall_score: overallScore,
    overall_confidence: overallConfidence,
    // No persona spread in canonical (single evaluator, not three) — the
    // dispersion line is a reviewer-panel concept and doesn't apply.
    overall_dispersion: null,
  };
}
