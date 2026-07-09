import { describe, it, expect } from 'vitest';
import { getDeskAttention, getDealAttentionReason } from '../dealState';
import type { Startup } from '../../types/startup';

// The helpers read only a handful of fields; a minimal shape is enough.
function startup(shape: Record<string, unknown>): Startup {
  return shape as unknown as Startup;
}

const NOW = new Date('2026-07-09T12:00:00Z').getTime();
const daysAgo = (n: number) => new Date(NOW - n * 24 * 60 * 60 * 1000).toISOString();

const escalated = startup({
  scout: { name: 'Escalated Co' },
  review: { overall_score: 8.4 },
  partner: { recommendation: 'INVEST', human_review_required: true },
  timestamps: { discovered_at: daysAgo(1) },
});
const fresh = startup({
  scout: { name: 'Fresh Co' },
  timestamps: { discovered_at: daysAgo(0) },
});
const stale = startup({
  scout: { name: 'Stale Co' },
  timestamps: { discovered_at: daysAgo(10) },
});
const reviewed = startup({
  scout: { name: 'Reviewed Co' },
  review: { overall_score: 6.2 },
  timestamps: { discovered_at: daysAgo(2) },
});
const resolved = startup({
  scout: { name: 'Resolved Co' },
  human_resolution: { resolved_at: daysAgo(1) },
});

describe('getDeskAttention', () => {
  it('excludes resolved deals and orders escalated → stale → reviewed → new', () => {
    const picked = getDeskAttention([fresh, resolved, reviewed, stale, escalated], 4, NOW);
    expect(picked.map((s) => s.scout.name)).toEqual([
      'Escalated Co',
      'Stale Co',
      'Reviewed Co',
      'Fresh Co',
    ]);
  });

  it('caps at the limit', () => {
    expect(getDeskAttention([fresh, reviewed, stale, escalated], 3, NOW)).toHaveLength(3);
  });

  it('breaks rank ties by age, oldest first', () => {
    const older = startup({ scout: { name: 'Older' }, timestamps: { discovered_at: daysAgo(3) } });
    const newer = startup({ scout: { name: 'Newer' }, timestamps: { discovered_at: daysAgo(1) } });
    expect(getDeskAttention([newer, older], 3, NOW).map((s) => s.scout.name)).toEqual([
      'Older',
      'Newer',
    ]);
  });
});

describe('getDealAttentionReason', () => {
  it.each([
    [escalated, 'Escalated — awaiting your ruling'],
    [stale, 'Waiting 10 days'],
    [reviewed, 'Reviewed at 6.2'],
    [fresh, 'New — awaiting review'],
  ])('%#', (s, reason) => {
    expect(getDealAttentionReason(s, NOW)).toBe(reason);
  });

  it('flags high-severity adverse items', () => {
    const adverse = startup({
      scout: { name: 'Adverse Co' },
      review: { overall_score: 5, diligence_red_flags: ['Founder dispute'] },
      timestamps: { discovered_at: daysAgo(1) },
    });
    expect(getDealAttentionReason(adverse, NOW)).toBe('Adverse signal on record');
  });
});
