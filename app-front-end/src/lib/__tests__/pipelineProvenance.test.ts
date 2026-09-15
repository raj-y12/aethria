import { describe, expect, it } from 'vitest';
import { buildPipelineProvenance } from '../pipelineProvenance';
import { buildMemoDecisionBrief } from '../memoDecisionBrief';
import type { Startup } from '../../types/startup';
import type { EvaluationRecord } from '../../api/evaluations';

const startup: Startup = {
  id: 's1',
  scout: { id: 's1', scout_type: 'test', name: 'Fixture', one_line: '', sector: '', why_now: '', confidence: 0.8 },
  review: { market_score: 9, overall_score: 9 },
  partner: { recommendation: 'INVEST' },
  agent_trace: { reviewer_run_id: 'r1', partner_run_id: 'p1' },
};
const evaluation: EvaluationRecord = {
  evaluation: {
    evaluation_id: 'ev1', evidence_snapshot_hash: 'snapshot1', policy_version_id: 'v1',
    policy_hash: 'policy1', rubric_version: 'rubric1', partner_rules_version: 'rules1',
    partner_rules_hash: 'hash1', model_manifest: {}, prompt_manifest: {}, status: 'completed',
  },
  criteria: [{
    criterion_assessment_id: 'ca1', criterion: 'market', score: 6, confidence: 0.7,
    evidence_sufficiency: 'sufficient', reasoning: 'Limited independent evidence.',
    supporting_claim_ids: ['claim1'], contradicting_claim_ids: [], missing_evidence: ['TAM'],
    quality_flags: [], deterministic_adjustments: { cap: 6 },
  }],
  recommendation: {
    recommendation_id: 'rec1', recommended_state: 'monitor', attention_priority: 1, confidence: 0.7,
    decision_drivers: ['Evidence limited'], principal_risks: [], mandate_conflicts: [], missing_information: [],
    change_conditions: [], human_review_required: true,
  },
};
function report(record: EvaluationRecord | null = evaluation) {
  return buildPipelineProvenance({ startup, evaluation: record, brief: buildMemoDecisionBrief({ evaluation: record }), scorecardEnabled: true });
}

describe('pipeline provenance report', () => {
  it('traces the displayed canonical score to its criterion, claims, snapshot and trace without replacing legacy values', () => {
    const original = JSON.stringify({ startup, evaluation });
    const result = report();
    expect(result.memo.overall_score).toBe(6);
    expect(result.memo.dimensions[0]).toMatchObject({
      score: 6, score_origin: 'CANONICAL_EVALUATION', legacy_score: 9, differs_from_legacy: true,
      criterion: { supporting_claim_ids: ['claim1'], deterministic_adjustments: { cap: 6 } },
    });
    expect(result.evaluation_manifest?.evidence_snapshot_hash).toBe('snapshot1');
    expect(result.agent_trace).toEqual(startup.agent_trace);
    expect(result.compatibility.visible_queue_recommendation).toBe('INVEST');
    expect(result.memo.system_lean).toBe('monitor');
    expect(JSON.stringify({ startup, evaluation })).toBe(original);
  });

  it('does not attribute a legacy score to a missing canonical evaluation', () => {
    const result = report(null);
    expect(result.memo.overall_score).toBeNull();
    expect(result.memo.score_origin).toBeNull();
    expect(result.compatibility.legacy_score_source).toBe('UNKNOWN_LEGACY');
    expect(result.memo.dimensions[0].differs_from_legacy).toBeNull();
  });

  it('observes the scorecard evidence block while retaining the underlying score for audit', () => {
    const result = report({ ...evaluation, recommendation: { ...evaluation.recommendation!, recommended_state: 'insufficient_evidence' } });
    expect(result.memo.overall_score).toBeNull();
    expect(result.memo.calculated_overall_score).toBe(6);
  });

  it('records human queue overrides separately from the original Partner recommendation', () => {
    const result = buildPipelineProvenance({ startup: { ...startup, human_resolution: { decision: 'NO' } }, brief: buildMemoDecisionBrief({}), scorecardEnabled: false });
    expect(result.compatibility.visible_queue_recommendation).toBe('PASS');
    expect(result.compatibility.queue_recommendation_source).toBe('HUMAN_OVERRIDE');
    expect(result.compatibility.partner?.recommendation).toBe('INVEST');
  });

  it('resolves the top-level opportunity from evaluation provenance when the startup projection is missing', () => {
    const result = buildPipelineProvenance({
      startup: { ...startup, canonical_opportunity_id: undefined },
      evaluation: { ...evaluation, provenance: { opportunity_id: 'opportunity-current' } },
      brief: buildMemoDecisionBrief({ evaluation }), scorecardEnabled: true,
    });
    expect(result.opportunity_id).toBe('opportunity-current');
    expect(result.opportunity_id_sources).toMatchObject({ resolved_from: 'evaluation_provenance', mismatch: false });
  });

  it('keeps an explicit mismatch when loaded provenance disagrees with the startup projection', () => {
    const result = buildPipelineProvenance({
      startup: { ...startup, canonical_opportunity_id: 'opportunity-stale' },
      evaluation: { ...evaluation, provenance: { opportunity_id: 'opportunity-current' } },
      brief: buildMemoDecisionBrief({ evaluation }), scorecardEnabled: true,
    });
    expect(result.opportunity_id).toBe('opportunity-current');
    expect(result.opportunity_id_sources).toMatchObject({ mismatch: true, startup_projection: 'opportunity-stale' });
  });
});

it('compares suppressed stored scores and identifies a stale Partner evaluation without changing the memo', () => {
  const result = buildPipelineProvenance({
    startup: {
      ...startup,
      review: { market_score: null },
      projection_provenance: {
        projection_origin: 'COMPATIBILITY_PROJECTION', legacy_score_origin: 'UNKNOWN_LEGACY',
        recorded_score_source: null, legacy_scores: { market_score: 9 },
        canonical_evaluation_id: 'old-evaluation', partner_recommendation: 'INVEST',
        partner_provenance: { evaluation_run_id: 'old-evaluation' }, human_override: null,
      },
    },
    evaluation, brief: buildMemoDecisionBrief({ evaluation }), scorecardEnabled: true,
  });
  expect(result.memo.score_origin).toBe('COMPATIBILITY_PROJECTION');
  expect(result.memo.overall_score).toBe(6);
  expect(result.memo.dimensions[0]).toMatchObject({ score_origin: 'CANONICAL_EVALUATION', legacy_score: 9, differs_from_legacy: true });
  expect(result.lineage.partner_uses_current_evaluation).toBe(false);
});
