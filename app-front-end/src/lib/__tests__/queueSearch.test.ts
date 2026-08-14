import { describe, expect, it } from 'vitest';
import { normalizeQuery, startupMatchesQuery } from '../queueSearch';
import type { Startup } from '../../types/startup';

function startup(overrides: Partial<Startup['scout']>): Startup {
  return {
    id: 'startup-1',
    scout: {
      id: 'scout-1',
      scout_type: 'generalist',
      name: 'Nuvia Bio',
      one_line: 'Protein design for rare disease',
      sector: 'Biotech',
      why_now: 'Cost curve',
      confidence: 0.7,
      ...overrides,
    },
  } as Startup;
}

describe('queueSearch', () => {
  it('matches every row on an empty query', () => {
    expect(startupMatchesQuery(startup({}), normalizeQuery('   '))).toBe(true);
  });

  it('matches a partial, case-insensitive name', () => {
    expect(startupMatchesQuery(startup({}), normalizeQuery('  NUV '))).toBe(true);
  });

  it('matches on sector and on the one-line', () => {
    expect(startupMatchesQuery(startup({}), normalizeQuery('biotech'))).toBe(true);
    expect(startupMatchesQuery(startup({}), normalizeQuery('rare disease'))).toBe(true);
  });

  it('does not match unrelated text', () => {
    expect(startupMatchesQuery(startup({}), normalizeQuery('fintech'))).toBe(false);
  });

  it('tolerates a missing one-line', () => {
    const row = startup({ one_line: undefined as unknown as string });
    expect(startupMatchesQuery(row, normalizeQuery('nuvia'))).toBe(true);
    expect(startupMatchesQuery(row, normalizeQuery('protein'))).toBe(false);
  });
});
