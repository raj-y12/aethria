import { describe, expect, it } from 'vitest';

import type { Startup } from '../../../types/startup';
import { buildInvestmentCase, buildSnapshotRows } from '../memoContentHelpers';

function startup(overrides: Partial<Startup>): Startup {
  return {
    id: 'editorial-fixture',
    scout: {
      id: 'editorial-fixture',
      scout_type: 'market_driven',
      name: 'Editorial Fixture',
      one_line: 'An insurance platform for technology companies.',
      sector: 'Insurtech',
      solution: 'Instant quotes and same-day binding for technology companies.',
      why_now: 'New AI liability creates demand for specialist underwriting.',
      confidence: 0.7,
    },
    timestamps: {},
    ...overrides,
  };
}

describe('memo editorial selection', () => {
  it('drops product repetition and generic mandate filler from Why Now', () => {
    const fixture = startup({
      partner: {
        recommendation: 'PASS',
        why_this_matters: 'Instant quotes and same-day binding for technology companies',
        market_insight: 'AI liability is creating a new specialist insurance category.',
        product_edge: 'Instant quotes and same-day binding for technology companies.',
      },
      review: {
        investment_thesis: [
          'Sector overlaps fund thesis targets',
          'Regulatory approvals remain the gating constraint on geographic expansion.',
        ],
      },
    });

    expect(buildInvestmentCase(fixture, [fixture.scout.solution ?? ''])).toEqual([
      'AI liability is creating a new specialist insurance category.',
      'Regulatory approvals remain the gating constraint on geographic expansion.',
      'New AI liability creates demand for specialist underwriting.',
    ]);
  });

  it('does not render an unfinished snapshot claim when a complete decision driver exists', () => {
    const fixture = startup({
      partner: {
        recommendation: 'PASS',
        snapshot: {
          one_liner: 'Insurance for technology companies.',
          key_signal: 'Corgi is an AI-native full-stack insurer backed',
        },
        decision_drivers: ['Regulatory execution remains unproven across target markets.'],
      },
    });

    expect(buildSnapshotRows(fixture, '')).toContainEqual({
      label: 'Why Aethria flagged it',
      text: 'Regulatory execution remains unproven across target markets.',
    });
  });
});
