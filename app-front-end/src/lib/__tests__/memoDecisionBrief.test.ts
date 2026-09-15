import { describe, expect, it } from 'vitest';

import type { EvaluationRecord } from '../../api/evaluations';
import type { EvidenceLedger } from '../../api/evidence';
import type { HumanRuling } from '../../api/decisions';
import { buildMemoDecisionBrief } from '../memoDecisionBrief';

const evaluation: EvaluationRecord = {
  evaluation: {
    evaluation_id: 'evaluation-1', evidence_snapshot_hash: 'snapshot-1',
    policy_version_id: 'policy-1', policy_hash: 'policy-hash', rubric_version: 'v1',
    partner_rules_version: 'v4', partner_rules_hash: 'rules-hash',
    model_manifest: {}, prompt_manifest: {}, status: 'completed',
  },
  criteria: [
    {
      criterion_assessment_id: 'criterion-regulatory', criterion: 'regulatory', score: 6,
      confidence: 0.92, evidence_sufficiency: 'sufficient', reasoning: 'Grounded.',
      supporting_claim_ids: ['claim-regulatory'], contradicting_claim_ids: [],
      missing_evidence: [], quality_flags: [],
    },
  ],
  recommendation: {
    recommendation_id: 'recommendation-1', recommended_state: 'advance', attention_priority: 3,
    confidence: 0.94, decision_drivers: ['strong_commit', 'Customer pull is sustained.', 'strong_commit', 'team_quality'],
    principal_risks: ['Expansion into Germany requires regulatory approval.'],
    mandate_conflicts: [], missing_information: [], change_conditions: [], human_review_required: true,
  },
};

const ledger: EvidenceLedger = {
  artifacts: [{
    artifact_id: 'artifact-regulator', artifact_type: 'registry', title: 'German regulator',
    source_uri: 'https://regulator.example/approval', trust_class: 'regulatory', access_class: 'public',
  }],
  evidence_items: [{
    evidence_item_id: 'item-regulatory', artifact_id: 'artifact-regulator', item_type: 'filing',
    display_excerpt: 'German expansion requires approval.', verification_state: 'verified',
    source_quality: 0.9, extraction_confidence: 0.9,
  }],
  claims: [{
    claim_id: 'claim-regulatory', company_id: 'company-1', claim_type: 'regulatory_expansion_risk',
    display_text: 'Expansion into Germany requires regulatory approval.',
    assertion_class: 'externally_verified', confidence: 0.9, material: true, status: 'current',
  }],
  links: [{
    link_id: 'link-regulatory', claim_id: 'claim-regulatory', evidence_item_id: 'item-regulatory',
    relationship: 'supports', support_strength: 0.9, rationale: 'Registry confirms the requirement.',
  }],
  plans: [],
};

describe('buildMemoDecisionBrief', () => {
  it('distinguishes a Partner diligence decision from historical insufficient evidence', () => {
    const result = buildMemoDecisionBrief({ evaluation: {
      ...evaluation,
      recommendation: { ...evaluation.recommendation!, recommended_state: 'insufficient_evidence' },
      provenance: {
        provenance_version: 'v1', pipeline_run_id: null, pipeline_entry_type: null,
        company_id: null, opportunity_id: null, scout_run_id: null,
        source_scout_pipeline_run_id: null, evaluation_run_id: 'evaluation-1',
        evidence_snapshot_hash: null, evidence_plan_id: null, evidence_artifact_ids: [],
        claim_ids: [], evidence_links: [], score_origin: 'REVIEWER_ASSESSMENT',
        score_schema_version: null, evaluation_rubric_version: null,
        reviewer_rules_version: null, partner_rules_version: null, thesis_version_id: null,
        policy_version: null, policy_hash: null, partner_rules_hash: null,
        recommendation_origin: 'PARTNER_ANALYSIS', canonical_recommendation: 'insufficient_evidence',
        human_review_required: true, criteria: [],
      },
    }, ledger });
    expect(result.lean).toBe('more_diligence');
    expect(result.leanProvenance).toBe('partner-judgment');
    expect(result.coverage).toBe('missing');
  });
  it('shows shared supporting evidence once while retaining every dimension', () => {
    const result = buildMemoDecisionBrief({ evaluation: { ...evaluation, criteria: [
      evaluation.criteria[0], { ...evaluation.criteria[0], criterion: 'market' },
    ] }, ledger });
    expect(result.claims).toHaveLength(1);
    expect(result.claims[0].criterion).toContain('market');
    expect(result.claims[0].criterion).toContain('regulatory');
    expect(result.claims[0].sources[0].href).toBe('https://regulator.example/approval');
  });
  it('blocks canonical insufficient evidence without inventing a machine lean', () => {
    const result = buildMemoDecisionBrief({
      evaluation: {
        ...evaluation,
        recommendation: { ...evaluation.recommendation!, recommended_state: 'insufficient_evidence' },
      },
      ledger,
    });

    expect(result.status).toBe('blocked');
    expect(result.lean).toBe('none');
    expect(result.coverage).toBe('missing');
  });

  it('prioritizes contradictory criterion evidence over canonical insufficient evidence', () => {
    const result = buildMemoDecisionBrief({
      evaluation: {
        ...evaluation,
        criteria: [{
          ...evaluation.criteria[0], evidence_sufficiency: 'contradictory',
          contradicting_claim_ids: ['claim-regulatory'],
        }],
        recommendation: { ...evaluation.recommendation!, recommended_state: 'insufficient_evidence' },
      },
      ledger,
    });

    expect(result.coverage).toBe('contradictory');
  });

  it('recognizes the exact canonical status-only decisive contradiction shape', () => {
    const result = buildMemoDecisionBrief({
      evaluation: {
        ...evaluation,
        criteria: [{
          ...evaluation.criteria[0],
          evidence_sufficiency: 'sufficient',
          contradicting_claim_ids: [],
        }],
        recommendation: {
          ...evaluation.recommendation!,
          recommended_state: 'insufficient_evidence',
          principal_risks: [],
          missing_information: [],
          change_conditions: [
            'rEsOlVe CoNtRaDiCtOrY eViDeNcE: Regulatory ban risk in primary market.',
          ],
          human_review_required: true,
        },
      },
      ledger,
    });

    expect(result.status).toBe('blocked');
    expect(result.coverage).toBe('contradictory');
  });

  it.each([
    'Resolve missing evidence: market.',
    'Discuss contradictory evidence with the founder.',
    'Resolve contradictory founder reports before approval.',
  ])('does not treat an unrelated condition as a canonical contradiction: %s', (condition) => {
    const result = buildMemoDecisionBrief({
      evaluation: {
        ...evaluation,
        recommendation: {
          ...evaluation.recommendation!,
          recommended_state: 'insufficient_evidence',
          change_conditions: [condition],
        },
      },
      ledger,
    });

    expect(result.coverage).toBe('missing');
  });

  it('keeps a legacy pass-like lean subordinate to missing or contradictory evidence', () => {
    const result = buildMemoDecisionBrief({
      evaluation: {
        ...evaluation,
        criteria: [{
          ...evaluation.criteria[0], evidence_sufficiency: 'contradictory',
          contradicting_claim_ids: ['claim-regulatory'],
        }],
        recommendation: { ...evaluation.recommendation!, recommended_state: 'pass' },
      },
      ledger,
    });

    expect(result.status).toBe('blocked');
    expect(result.lean).toBe('pass');
    expect(result.coverage).toBe('contradictory');
  });

  it('keeps an evidence block visible after a human ruling is recorded', () => {
    const result = buildMemoDecisionBrief({
      evaluation: {
        ...evaluation,
        criteria: [{
          ...evaluation.criteria[0], evidence_sufficiency: 'contradictory',
          contradicting_claim_ids: ['claim-regulatory'],
        }],
      },
      ledger,
      ruling: { ruling_id: 'ruling-1', decision: 'pass', rationale: 'The fund declines despite the conflict.' },
    });

    expect(result.status).toBe('blocked');
    expect(result.ruling).toMatchObject({ decision: 'pass', rationale: 'The fund declines despite the conflict.' });
  });

  it('keeps status, lean, mandate, coverage, agreement, and recorded ruling distinct', () => {
    const ruling: HumanRuling = {
      ruling_id: 'ruling-1', decision: 'monitor', rationale: 'Wait for expansion evidence.',
    };
    const result = buildMemoDecisionBrief({
      evaluation: {
        ...evaluation,
        recommendation: {
          ...evaluation.recommendation!, recommended_state: 'advance',
          mandate_conflicts: ['Does not meet the climate mandate.'],
        },
      },
      ledger,
      ruling,
    });

    expect(result).toMatchObject({
      status: 'recorded', lean: 'advance', mandate: 'conflicted',
      coverage: 'sufficient', agreement: 'unknown',
      ruling: { decision: 'monitor', rationale: 'Wait for expansion evidence.' },
    });
  });

  it('does not infer affirmative mandate alignment from an empty conflicts list', () => {
    const result = buildMemoDecisionBrief({ evaluation, ledger });

    expect(result.mandate).toBe('unknown');
  });

  it('never exposes a confidence field or percentage-formatted value', () => {
    const result = buildMemoDecisionBrief({ evaluation, ledger });
    const serialized = JSON.stringify(result).toLowerCase();

    expect(serialized).not.toContain('confidence');
    expect(serialized).not.toMatch(/\d+(?:\.\d+)?%/);
  });

  it('limits independent drivers to three, joins criterion claims to stored sources, and orders output deterministically', () => {
    const result = buildMemoDecisionBrief({ evaluation, ledger });

    expect(result.drivers).toEqual([
      'Scores clear the commit bar',
      'Customer pull is sustained.',
      'Team quality',
    ]);
    expect(result.claims).toEqual([{
      claimId: 'claim-regulatory', claim: 'Expansion into Germany requires regulatory approval.',
      criterion: 'regulatory', relationship: 'supports', provenance: 'verified',
      sources: [{ artifactId: 'artifact-regulator', title: 'German regulator', href: 'https://regulator.example/approval' }],
    }]);
  });

  it('does not use a contradicting link to verify a supporting claim entry', () => {
    const result = buildMemoDecisionBrief({
      evaluation,
      ledger: {
        ...ledger,
        links: [{ ...ledger.links[0], relationship: 'contradicts' }],
      },
    });

    expect(result.claims).toMatchObject([{
      claimId: 'claim-regulatory', relationship: 'supports', provenance: 'missing', sources: [],
    }]);
  });

  it('labels provenance conservatively', () => {
    const result = buildMemoDecisionBrief({
      evaluation: {
        ...evaluation,
        criteria: [
          { ...evaluation.criteria[0], criterion: 'founder', supporting_claim_ids: ['claim-founder'] },
          { ...evaluation.criteria[0], criterion: 'product', supporting_claim_ids: ['claim-model'] },
          { ...evaluation.criteria[0], criterion: 'market', supporting_claim_ids: [] },
        ],
      },
      ledger: {
        ...ledger,
        claims: [
          ...ledger.claims,
          { ...ledger.claims[0], claim_id: 'claim-founder', assertion_class: 'founder_asserted', display_text: 'Founder reports 12 pilots.' },
          { ...ledger.claims[0], claim_id: 'claim-model', assertion_class: 'model_inferred', display_text: 'Model infers concentration risk.' },
        ],
      },
    });

    expect(result.claims.map((claim) => [claim.claimId, claim.provenance])).toEqual([
      ['claim-founder', 'reported'],
      ['claim-model', 'model-derived'],
    ]);
    expect(result.derivations).toEqual([{ criterion: 'market', provenance: 'rule-derived' }]);
  });

  it('does not double-report an unscored criterion as both a gap and a claim-provenance derivation', () => {
    const result = buildMemoDecisionBrief({
      evaluation: {
        ...evaluation,
        criteria: [
          { ...evaluation.criteria[0], criterion: 'market', supporting_claim_ids: [], missing_evidence: ['market'] },
          { ...evaluation.criteria[0], criterion: 'execution', supporting_claim_ids: [], missing_evidence: ['execution'] },
        ],
        recommendation: {
          ...evaluation.recommendation!,
          principal_risks: [],
          change_conditions: ['Resolve missing evidence: market.', 'Resolve missing evidence: execution.'],
        },
      },
      ledger,
    });

    // Both criteria are genuine gaps — that's real, distinct diligence work.
    expect(result.risks.map(({ key }) => key).sort()).toEqual(['execution', 'market']);
    // Neither should also show up as an empty "rule-derived" claim-provenance row —
    // that would just restate the same gap a second time.
    expect(result.derivations).toEqual([]);
  });

  it('groups regulatory, licensing, and jurisdiction expansion paraphrases without inventing sources for free text', () => {
    const result = buildMemoDecisionBrief({
      evaluation: {
        ...evaluation,
        criteria: [{
          ...evaluation.criteria[0], missing_evidence: ['UK licensing requirements for jurisdiction expansion remain unclear.'],
        }],
        recommendation: {
          ...evaluation.recommendation!,
          principal_risks: [
            'Expansion into Germany requires regulatory approval.',
            'Corgi needs licensing before expanding into new jurisdictions.',
          ],
        },
      },
      ledger,
    });

    expect(result.risks).toEqual([{
      key: 'regulatory-expansion',
      text: 'UK licensing requirements for jurisdiction expansion remain unclear.',
      kind: 'risk', severity: 'high',
    }]);
    expect(result.claims[0].sources).toEqual([
      { artifactId: 'artifact-regulator', title: 'German regulator', href: 'https://regulator.example/approval' },
    ]);
  });

  it('deduplicates missing and contradictory resolution boilerplate by normalized subject', () => {
    const result = buildMemoDecisionBrief({
      evaluation: {
        ...evaluation,
        recommendation: {
          ...evaluation.recommendation!,
          principal_risks: ['Market concentration'],
          missing_information: ['market'],
          change_conditions: [
            'Resolve missing evidence: market.',
            'Resolve contradictory evidence: Market concentration.',
          ],
        },
      },
      ledger,
    });

    expect(result.risks).toHaveLength(2);
    expect(result.risks.map(({ key, kind }) => ({ key, kind }))).toEqual([
      { key: 'market', kind: 'gap' },
      { key: 'market-concentration', kind: 'risk' },
    ]);
  });

  it('excludes internal score-gap and reviewer-spread diagnostics from company risks', () => {
    const result = buildMemoDecisionBrief({
      evaluation: {
        ...evaluation,
        criteria: [{
          ...evaluation.criteria[0],
          missing_evidence: ['Gap >=4 between market and product scores.', 'Reviewer spread is 5.2 points.'],
          quality_flags: ['reviewer_spread'],
        }],
        recommendation: {
          ...evaluation.recommendation!,
          principal_risks: ['Gap >=4 between criteria.', 'Reviewer spread indicates disagreement.'],
        },
      },
      ledger,
    });

    expect(result.risks).toEqual([]);
  });
});
