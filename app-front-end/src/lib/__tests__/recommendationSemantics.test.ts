import { describe, expect, it } from 'vitest';
import {
  defaultRulingForRecommendation,
  recommendationSemantics,
  rulingAlignsWithRecommendation,
  partnerRecommendationLabel,
} from '../recommendationSemantics';

describe('institutional recommendation semantics', () => {
  it('displays the canonical diligence action instead of its legacy Monitor projection', () => {
    expect(partnerRecommendationLabel({ recommendation: 'MONITOR', provenance: {
      original_recommendation_origin: 'PARTNER_ANALYSIS', recommendation_origin: 'PARTNER_ANALYSIS',
      canonical_recommendation: 'insufficient_evidence',
    } })).toBe('More diligence');
  });
  it('keeps canonical opportunity More diligence distinct from historical Monitor', () => {
    expect(partnerRecommendationLabel({ recommendation: 'MONITOR', provenance: {
      original_recommendation_origin: 'CANONICAL_EVALUATION', recommendation_origin: 'PARTNER_CANONICAL_MAPPING',
      canonical_recommendation: 'insufficient_evidence',
    } })).toBe('More diligence');
    expect(partnerRecommendationLabel({ recommendation: 'MONITOR', provenance: {
      original_recommendation_origin: 'CANONICAL_EVALUATION', recommendation_origin: 'PARTNER_CANONICAL_MAPPING',
      canonical_recommendation: 'monitor',
    } })).toBe('Monitor');
  });
  it.each([
    ['advance', 'advance', true],
    ['monitor', 'monitor', true],
    ['pass', 'pass', true],
    ['advance', 'pass', false],
    ['pass', 'monitor', false],
    ['insufficient_evidence', 'advance', false],
    ['insufficient_evidence', 'monitor', false],
    ['insufficient_evidence', 'pass', false],
  ] as const)('%s and %s alignment is %s', (recommendation, ruling, aligned) => {
    expect(rulingAlignsWithRecommendation(recommendation, ruling)).toBe(aligned);
  });

  it('keeps insufficient evidence non-decisive', () => {
    expect(defaultRulingForRecommendation('insufficient_evidence')).toBeNull();
    expect(recommendationSemantics('insufficient_evidence').label).toBe(
      'Insufficient evidence',
    );
  });
});

it('uses actual operational actions ahead of lossy compatibility recommendations', () => {
  expect(partnerRecommendationLabel({ recommendation: 'INVEST', judgment_action: 'ADVANCE', operational_action: 'ADVANCE' })).toBe('Advance');
  expect(partnerRecommendationLabel({ recommendation: 'MONITOR', judgment_action: 'ADVANCE', operational_action: 'MORE_DILIGENCE' })).toBe('More diligence');
});
