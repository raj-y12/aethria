import { describe, expect, it } from 'vitest';
import { rowLeadRisk } from '../queueRowShared';
import type { Startup } from '../../../types/startup';

const startup = (overrides: Partial<Startup>) => ({ scout: { name: 'X' }, ...overrides }) as Startup;

describe('rowLeadRisk', () => {
  it('prefers the canonical partner judgment over the reviewer', () => {
    const s = startup({
      current_analysis: { partner: { judgment: { principal_risks: ['Runway risk'] } } } as Startup['current_analysis'],
      review: { key_risks: ['Legacy risk'] },
    });
    expect(rowLeadRisk(s)).toBe('Runway risk');
  });

  it('falls back to the reviewer key risk', () => {
    expect(rowLeadRisk(startup({ review: { key_risks: [' Legacy risk '] } }))).toBe('Legacy risk');
  });

  it('returns null when no risk is recorded', () => {
    expect(rowLeadRisk(startup({}))).toBeNull();
    expect(rowLeadRisk(startup({ review: { key_risks: ['  '] } }))).toBeNull();
  });
});
