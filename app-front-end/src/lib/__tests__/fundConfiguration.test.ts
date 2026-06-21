import { describe, it, expect } from 'vitest';
import {
  DEFAULT_VERDICT_BADGES,
  badgeTextColorForBackground,
  createDefaultFundConfiguration,
} from '../fundConfiguration';

describe('createDefaultFundConfiguration', () => {
  const config = createDefaultFundConfiguration();

  it('exposes the six canonical verdict badges in order', () => {
    expect(config.verdictBadges.map((b) => b.id)).toEqual([
      'INVEST',
      'MONITOR',
      'PASS',
      'STRONG',
      'MEDIUM',
      'WEAK',
    ]);
  });

  it('exposes the partner verdict score bands (Pass/Monitor/Invest)', () => {
    expect(config.scoreBands.map((b) => b.label)).toEqual(['Pass', 'Monitor', 'Invest']);
  });

  it('keeps DEFAULT_VERDICT_BADGES aligned with emitted verdicts', () => {
    expect(DEFAULT_VERDICT_BADGES.map((b) => b.id)).toEqual([
      'INVEST',
      'MONITOR',
      'PASS',
      'STRONG',
      'MEDIUM',
      'WEAK',
    ]);
  });
});

describe('weight sanitization (corrupt saved config)', () => {
  it('drops a non-finite saved weight back to the canonical default', () => {
    const cfg = createDefaultFundConfiguration({
      fund_config: {
        scoringWeights: [
          { key: 'market', weight: Number.NaN, label: 'Market', description: '' },
          { key: 'product', weight: 'oops', label: 'Product', description: '' },
        ],
      },
    } as never);
    // A NaN/string weight must not survive — it would make computeConfiguredScore
    // return NaN and mislabel every startup "Invest".
    expect(cfg.scoringWeights.every((w) => Number.isFinite(w.weight))).toBe(true);
  });
});

describe('badgeTextColorForBackground', () => {
  it('uses dark text on light backgrounds', () => {
    expect(badgeTextColorForBackground('#ffffff')).toBe('#1a2b48');
  });

  it('uses light text on dark backgrounds', () => {
    expect(badgeTextColorForBackground('#1a2b48')).toBe('#fffdf7');
  });
});
