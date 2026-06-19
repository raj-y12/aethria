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

describe('badgeTextColorForBackground', () => {
  it('uses dark text on light backgrounds', () => {
    expect(badgeTextColorForBackground('#ffffff')).toBe('#1a2b48');
  });

  it('uses light text on dark backgrounds', () => {
    expect(badgeTextColorForBackground('#1a2b48')).toBe('#fffdf7');
  });
});
