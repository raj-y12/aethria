import { describe, expect, it } from 'vitest';
import {
  domainLabel,
  evidenceLabels,
  identityConfidence,
  isBestIdentityMatch,
} from '../candidateIdentity';

describe('candidate identity presentation', () => {
  it('turns resolver confidence into bounded analyst-facing language', () => {
    expect(identityConfidence(0.91)).toBe('Strong identity match');
    expect(identityConfidence(0.64)).toBe('Likely identity match');
    expect(identityConfidence(-2)).toBe('Possible identity match');
    expect(identityConfidence(4)).toBe('Strong identity match');
  });

  it('normalizes evidence labels without inventing verification', () => {
    expect(evidenceLabels(['official', 'linkedin', 'crunchbase', 'news'])).toEqual([
      'Official site', 'LinkedIn', 'Crunchbase', 'Press',
    ]);
    expect(evidenceLabels([])).toEqual([]);
    expect(evidenceLabels(['unknown-badge'])).toEqual([]);
  });

  it('marks only a strong first candidate as the best match', () => {
    expect(isBestIdentityMatch({ confidence: 0.82 } as never, 0)).toBe(true);
    expect(isBestIdentityMatch({ confidence: 0.69 } as never, 0)).toBe(false);
    expect(isBestIdentityMatch({ confidence: 0.82 } as never, 1)).toBe(false);
  });

  it('renders a clean registrable domain label', () => {
    expect(domainLabel('https://www.acme.ie/about')).toBe('acme.ie');
    expect(domainLabel('not a website')).toBe('');
  });
});
