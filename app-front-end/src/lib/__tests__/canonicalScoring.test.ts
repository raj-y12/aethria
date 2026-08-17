import { describe, expect, it } from 'vitest';
import { canonicalCriteriaToStructuredScoring } from '../canonicalScoring';
import type { CriterionAssessment, EvaluationRecord } from '../../api/evaluations';

function criterion(overrides: Partial<CriterionAssessment> & { criterion: string }): CriterionAssessment {
  return {
    criterion_assessment_id: `ca-${overrides.criterion}`,
    score: 7,
    confidence: 0.8,
    evidence_sufficiency: 'sufficient',
    reasoning: 'Grounded in evidence.',
    supporting_claim_ids: [],
    contradicting_claim_ids: [],
    missing_evidence: [],
    quality_flags: [],
    ...overrides,
  };
}

function evaluationRecord(criteria: CriterionAssessment[]): EvaluationRecord {
  return {
    evaluation: {
      evaluation_id: 'eval-1',
      evidence_snapshot_hash: 'hash',
      policy_version_id: 'v4',
      policy_hash: 'policy-hash',
      rubric_version: 'tenant-rubric:v4',
      partner_rules_version: 'v4',
      partner_rules_hash: 'rules-hash',
      model_manifest: {},
      prompt_manifest: {},
      status: 'completed',
    },
    criteria,
    recommendation: null,
  };
}

describe('canonicalCriteriaToStructuredScoring', () => {
  it('returns null when there are no canonical criteria yet', () => {
    expect(canonicalCriteriaToStructuredScoring(null)).toBeNull();
    expect(canonicalCriteriaToStructuredScoring(evaluationRecord([]))).toBeNull();
  });

  it('maps the five fixed criteria onto the scorecard shape', () => {
    const record = evaluationRecord([
      criterion({ criterion: 'market', score: 8 }),
      criterion({ criterion: 'product', score: 6 }),
      criterion({ criterion: 'technical', score: 7 }),
      criterion({ criterion: 'execution', score: 5 }),
      criterion({ criterion: 'defensibility', score: 4 }),
    ]);

    const scoring = canonicalCriteriaToStructuredScoring(record);

    expect(scoring).not.toBeNull();
    expect(scoring!.market.score).toBe(8);
    expect(scoring!.market.unscored).toBe(false);
    expect(scoring!.defensibility.score).toBe(4);
    // Overall excludes defensibility, matching AssessmentScorecard's own convention.
    expect(scoring!.overall_score).toBeCloseTo((8 + 6 + 7 + 5) / 4);
    expect(scoring!.policy_version_id).toBe('v4');
  });

  it('marks a dimension unscored when its score is null, and falls back to reasoning text', () => {
    const record = evaluationRecord([
      criterion({ criterion: 'market', score: null, evidence_sufficiency: 'insufficient', reasoning: 'No evidence found.' }),
    ]);

    const scoring = canonicalCriteriaToStructuredScoring(record);

    expect(scoring!.market.unscored).toBe(true);
    expect(scoring!.market.components).toEqual({});
    expect(scoring!.market.reasoning).toEqual(['No evidence found.']);
    // A dimension absent from criteria entirely is also unscored, not a crash.
    expect(scoring!.defensibility.unscored).toBe(true);
  });

  it('excludes unscored drivers from the overall mean instead of averaging in a placeholder 0', () => {
    const record = evaluationRecord([
      criterion({ criterion: 'market', score: 9 }),
      criterion({ criterion: 'product', score: null, evidence_sufficiency: 'insufficient' }),
    ]);

    const scoring = canonicalCriteriaToStructuredScoring(record);

    expect(scoring!.overall_score).toBe(9);
  });
});
