import { describe, it, expect } from 'vitest';
import {
  commitScoreInput,
  formatReviewerAvg,
  getDecisionThresholdBoundaries,
  validateDecisionThresholds,
  applyDecisionThresholds,
} from '../decisionThresholds';
import { createDefaultFundConfiguration } from '../fundConfiguration';

describe('commitScoreInput', () => {
  it('parses a valid integer', () => {
    expect(commitScoreInput('50', 0, 100, 10)).toBe(50);
  });

  it('falls back when empty or non-numeric', () => {
    expect(commitScoreInput('', 0, 100, 10)).toBe(10);
    expect(commitScoreInput('abc', 0, 100, 10)).toBe(10);
  });

  it('clamps to the provided range', () => {
    expect(commitScoreInput('150', 0, 100, 10)).toBe(100);
    expect(commitScoreInput('-5', 0, 100, 10)).toBe(0);
  });
});

describe('formatReviewerAvg', () => {
  it('renders a 0–100 score as a 0–10 figure with one decimal', () => {
    expect(formatReviewerAvg(74)).toBe('7.4');
    expect(formatReviewerAvg(100)).toBe('10.0');
  });
});

describe('decision threshold boundaries', () => {
  const config = createDefaultFundConfiguration();

  it('produces an ordered auto-pass < pass/monitor < monitor/invest set', () => {
    const b = getDecisionThresholdBoundaries(config);
    expect(b.autoPassCeiling).toBeLessThan(b.passMonitorBoundary);
    expect(b.passMonitorBoundary).toBeLessThan(b.monitorInvestBoundary);
  });

  it('validates the default configuration as consistent', () => {
    expect(validateDecisionThresholds(config).valid).toBe(true);
  });

  it('round-trips an applied patch through the boundaries', () => {
    const patched = applyDecisionThresholds(config, {
      passMonitorBoundary: 55,
      monitorInvestBoundary: 78,
    });
    const b = getDecisionThresholdBoundaries(patched);
    expect(b.passMonitorBoundary).toBe(55);
    expect(b.monitorInvestBoundary).toBe(78);
    expect(validateDecisionThresholds(patched).valid).toBe(true);
  });

  it('repairs an inverted monitor/invest boundary instead of producing invalid config', () => {
    const patched = applyDecisionThresholds(config, {
      passMonitorBoundary: 80,
      monitorInvestBoundary: 50, // below pass/monitor — must be corrected
    });
    const b = getDecisionThresholdBoundaries(patched);
    expect(b.monitorInvestBoundary).toBeGreaterThan(b.passMonitorBoundary);
  });
});
