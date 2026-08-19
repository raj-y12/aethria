import { describe, expect, it } from 'vitest';
import { getTriageGateStatus } from '../triageGate';
import type { Startup } from '../../types/startup';

function baseStartup(overrides: Partial<Startup> = {}): Startup {
  return {
    id: 's-1',
    scout: {
      id: 's-1',
      scout_type: 'market_driven',
      name: 'Acme',
      one_line: 'x',
      sector: 'B2B SaaS',
      why_now: 'now',
      confidence: 0.9,
    },
    review: null,
    partner: null,
    ...overrides,
  };
}

describe('getTriageGateStatus', () => {
  it('gates an unreviewed startup below the confidence threshold', () => {
    const startup = baseStartup({ scout: { ...baseStartup().scout, confidence: 0.1 } });
    const status = getTriageGateStatus(startup);
    expect(status).toEqual({
      gated: true,
      reason: 'not_reviewed',
      confidence: 0.1,
      threshold: 0.3,
    });
  });

  it('does not gate an unreviewed startup at or above the confidence threshold', () => {
    // Regression: an unreviewed startup used to always report "held by
    // triage funnel" regardless of confidence, so a 64%-confidence startup
    // that just hadn't had its cycle yet showed "confidence 64% is below
    // the 30% review bar" -- true, low confidence isn't why it was
    // unreviewed. Live-reported by Raj 2026-08-19.
    const startup = baseStartup({ scout: { ...baseStartup().scout, confidence: 0.64 } });
    expect(getTriageGateStatus(startup)).toEqual({ gated: false });
  });

  it('does not gate a reviewed-and-decided startup', () => {
    const startup = baseStartup({
      review: { market_score: 8, product_score: 8, technical_score: 8, execution_score: 8 },
      partner: { recommendation: 'INVEST' } as Startup['partner'],
    });
    expect(getTriageGateStatus(startup)).toEqual({ gated: false });
  });

  it('gates a reviewed-but-undecided startup below the decision threshold', () => {
    const startup = baseStartup({
      review: { market_score: 4, product_score: 4, technical_score: 4, execution_score: 4 },
      partner: null,
    });
    expect(getTriageGateStatus(startup)).toEqual({
      gated: true,
      reason: 'not_decided',
      overallScore: 4,
      threshold: 0.55,
    });
  });

  it('does not gate a reviewed-but-undecided startup at or above the decision threshold', () => {
    const startup = baseStartup({
      review: { market_score: 6, product_score: 6, technical_score: 6, execution_score: 6 },
      partner: null,
    });
    expect(getTriageGateStatus(startup)).toEqual({ gated: false });
  });

  it('does not gate when the overall score is unparseable (ambiguous with an in-flight decision)', () => {
    const startup = baseStartup({
      review: { market_score: 4, product_score: 4, technical_score: undefined, execution_score: 4 },
      partner: null,
    });
    expect(getTriageGateStatus(startup)).toEqual({ gated: false });
  });
});
