import { describe, expect, it } from 'vitest';
import {
  domainLabel,
  evidenceLabels,
  identityConfidence,
  isBestIdentityMatch,
} from '../candidateIdentity';

describe('candidate identity presentation', () => {
  it('turns resolver confidence into bounded analyst-facing language', () => {
    expect(identityConfidence(0.91)).toEqual({ label: 'Strong identity match', percent: 91, tone: 'strong' });
    expect(identityConfidence(0.64)).toEqual({ label: 'Likely identity match', percent: 64, tone: 'likely' });
    expect(identityConfidence(-2)).toEqual({ label: 'Possible identity match', percent: 0, tone: 'possible' });
    expect(identityConfidence(4)).toEqual({ label: 'Strong identity match', percent: 100, tone: 'strong' });
  });

  it('normalizes evidence labels and falls back to an official-domain claim', () => {
    expect(evidenceLabels(['official', 'linkedin', 'crunchbase', 'news'], true)).toEqual([
      'Official site', 'LinkedIn', 'Crunchbase', 'Press',
    ]);
    expect(evidenceLabels([], true)).toEqual(['Official domain candidate']);
    expect(evidenceLabels([], false)).toEqual([]);
  });

  it('marks the first highest-confidence strong candidate as the best match', () => {
    const candidates = [{ confidence: 0.64 }, { confidence: 0.82 }, { confidence: 0.82 }] as never;
    expect(isBestIdentityMatch(candidates[0], 0, candidates)).toBe(false);
    expect(isBestIdentityMatch(candidates[1], 1, candidates)).toBe(true);
    expect(isBestIdentityMatch(candidates[2], 2, candidates)).toBe(false);
    expect(isBestIdentityMatch({ confidence: 0.69 } as never, 0, [{ confidence: 0.69 }] as never)).toBe(false);
  });

  it('renders a clean registrable domain label', () => {
    expect(domainLabel('https://www.acme.ie/about')).toBe('acme.ie');
    expect(domainLabel('not a website')).toBe('');
  });
});
