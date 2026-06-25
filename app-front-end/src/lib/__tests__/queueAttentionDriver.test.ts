import { describe, it, expect } from 'vitest';
import {
  getConvictionTier,
  getVisibleRecommendation,
  getQueueConvictionPct,
  formatQueueConviction,
  type QueueRowContext,
} from '../queueAttentionDriver';
import { buildResolutionLine } from '../productChromeMappers';
import type { Startup } from '../../types/startup';

// The driver functions read only a handful of fields; a minimal shape is enough.
function startup(shape: Record<string, unknown>): Startup {
  return shape as unknown as Startup;
}

// getQueueConvictionPct only reads startup + configuredScore off the context.
function ctx(shape: { startup: Startup; configuredScore: number }): QueueRowContext {
  return shape as unknown as QueueRowContext;
}

describe('getConvictionTier (thresholds 45 / 72)', () => {
  it.each([
    [null, 'none'],
    [Number.NaN, 'none'],
    [0, 'low'],
    [44, 'low'],
    [45, 'mid'],
    [71, 'mid'],
    [72, 'high'],
    [100, 'high'],
  ])('pct %s -> %s', (pct, tier) => {
    expect(getConvictionTier(pct as number | null)).toBe(tier);
  });
});

describe('getVisibleRecommendation', () => {
  it('human ruling wins over partner recommendation', () => {
    expect(
      getVisibleRecommendation(
        startup({ human_resolution: { decision: 'YES' }, partner: { recommendation: 'PASS' } }),
      ),
    ).toBe('INVEST');
    expect(getVisibleRecommendation(startup({ human_resolution: { decision: 'NO' } }))).toBe('PASS');
    expect(getVisibleRecommendation(startup({ human_resolution: { decision: 'MAYBE' } }))).toBe(
      'MONITOR',
    );
  });

  it('falls back to partner recommendation, else null', () => {
    expect(getVisibleRecommendation(startup({ partner: { recommendation: 'MONITOR' } }))).toBe(
      'MONITOR',
    );
    expect(getVisibleRecommendation(startup({}))).toBeNull();
  });
});

describe('getQueueConvictionPct / formatQueueConviction', () => {
  it('scales a 0-10 overall score to 0-100', () => {
    expect(getQueueConvictionPct(ctx({ startup: startup({ review: { overall_score: 7 }, scout: {} }), configuredScore: 0 }))).toBe(70);
  });

  it('passes through an already-0-100 score', () => {
    expect(getQueueConvictionPct(ctx({ startup: startup({ review: { overall_score: 85 }, scout: {} }), configuredScore: 0 }))).toBe(85);
  });

  it('falls back to configuredScore, then scout confidence, then null', () => {
    expect(getQueueConvictionPct(ctx({ startup: startup({ scout: {} }), configuredScore: 60 }))).toBe(60);
    expect(
      getQueueConvictionPct(ctx({ startup: startup({ scout: { confidence: 0.4 } }), configuredScore: 0 })),
    ).toBe(40);
    expect(getQueueConvictionPct(ctx({ startup: startup({ scout: {} }), configuredScore: 0 }))).toBeNull();
  });

  it('formats as x.x/10, or em-dash when unknown', () => {
    expect(formatQueueConviction(ctx({ startup: startup({ review: { overall_score: 7 }, scout: {} }), configuredScore: 0 }))).toBe('7.0/10');
    expect(formatQueueConviction(ctx({ startup: startup({ scout: {} }), configuredScore: 0 }))).toBe('—');
  });
});

describe('buildResolutionLine', () => {
  it('is undefined for a clean FOUND/empty resolution', () => {
    expect(buildResolutionLine(startup({ scout: { resolution_status: 'FOUND' } }))).toBeUndefined();
    expect(buildResolutionLine(startup({ scout: {} }))).toBeUndefined();
  });

  it('summarizes evidence count and missing fields for a weak resolution', () => {
    const line = buildResolutionLine(
      startup({
        scout: {
          resolution_status: 'PARTIAL',
          company_resolution: {
            missing_fields: ['website'],
            evidence_sources: [{}, {}],
          },
        },
      }),
    );
    expect(line).toBeDefined();
    expect(line).toContain('2 sources');
    expect(line).toContain('missing');
  });
});
