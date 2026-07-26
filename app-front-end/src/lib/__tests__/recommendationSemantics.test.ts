import { describe, expect, it } from 'vitest';
import {
  defaultRulingForRecommendation,
  recommendationSemantics,
  rulingAlignsWithRecommendation,
} from '../recommendationSemantics';

describe('institutional recommendation semantics', () => {
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
