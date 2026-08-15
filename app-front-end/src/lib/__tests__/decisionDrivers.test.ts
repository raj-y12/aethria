import { describe, expect, it } from 'vitest';

import {
  formatDecisionDriver,
  formatDecisionDrivers,
  isDecisionDriverTag,
} from '../decisionDrivers';

describe('decision drivers are machine tags, not prose', () => {
  it('renders a known tag as a sentence', () => {
    // This is the one that shipped: "critical_risk" appeared as a bullet in the
    // memo's Why Now list.
    expect(formatDecisionDriver('critical_risk')).toBe(
      'A critical risk blocks the recommendation',
    );
  });

  it('de-slugs an unknown tag instead of dropping it', () => {
    expect(formatDecisionDriver('some_future_tag')).toBe('Some future tag');
  });

  it('passes a written sentence through untouched', () => {
    const prose = 'Customer pull is promising.';
    expect(formatDecisionDriver(prose)).toBe(prose);
    expect(isDecisionDriverTag(prose)).toBe(false);
  });

  it('drops empties when formatting a list', () => {
    expect(formatDecisionDrivers(['critical_risk', '', '  '])).toEqual([
      'A critical risk blocks the recommendation',
    ]);
    expect(formatDecisionDrivers(undefined)).toEqual([]);
  });
});
