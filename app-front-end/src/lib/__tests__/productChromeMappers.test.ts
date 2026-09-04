import { describe, expect, it } from 'vitest';
import { buildLookupSnapshotProps } from '../productChromeMappers';
import type { Startup } from '../../types/startup';
import type { CriterionAssessment, EvaluationRecord } from '../../api/evaluations';

function startup(overrides: Partial<Startup> = {}): Startup {
  return {
    id: 'startup-1',
    scout: {
      id: 'scout-1',
      scout_type: 'market_driven',
      name: 'Notion Labs',
      one_line: 'Productivity software.',
      sector: 'Productivity',
      why_now: 'Now.',
      confidence: 0.8,
    },
    review: {
      market_score: 8,
      product_score: 6,
      technical_score: 7,
      execution_score: 5,
      defensibility_score: 4,
      overall_summary: 'Strong candidate.',
    },
    ...overrides,
  };
}

function criterion(overrides: Partial<CriterionAssessment> & { criterion: string }): CriterionAssessment {
  return {
    criterion_assessment_id: `ca-${overrides.criterion}`,
    score: null,
    confidence: 0,
    evidence_sufficiency: 'insufficient',
    reasoning: 'No evidence found.',
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

describe('buildLookupSnapshotProps', () => {
  it('does not render a score snapshot without a canonical evaluation', () => {
    expect(buildLookupSnapshotProps(startup(), undefined, undefined, null)).toBeNull();
  });

  it('shows a dimension as unscored (null) when canonical evidence is insufficient, even though legacy has a number', () => {
    // Regression: the dispatch snapshot used to read only legacy review.product_score,
    // showing "6" even when the canonical evaluation (which the full memo reads)
    // correctly left the dimension unscored for lack of evidence.
    const evaluation = evaluationRecord([
      criterion({ criterion: 'market' }),
      criterion({ criterion: 'execution' }),
      criterion({ criterion: 'product' }),
      criterion({ criterion: 'technical' }),
      criterion({ criterion: 'defensibility' }),
    ]);

    const props = buildLookupSnapshotProps(startup(), undefined, undefined, evaluation);
    const product = props!.dimensions.find((d) => d.key === 'product');
    expect(product?.score).toBeNull();
  });

  it('prefers a real canonical score over the legacy one when both exist', () => {
    const evaluation = evaluationRecord([
      criterion({ criterion: 'market', score: 3, confidence: 0.9, evidence_sufficiency: 'sufficient' }),
    ]);

    const props = buildLookupSnapshotProps(startup(), undefined, undefined, evaluation);
    const market = props!.dimensions.find((d) => d.key === 'market');
    expect(market?.score).toBe(3);
  });
});
