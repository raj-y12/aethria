import { describe, expect, it } from 'vitest';
import { buildPositionRows, sectorConcentration } from '../positionRows';
import type { PortfolioPosition } from '../../../api/portfolio';
import type { Startup } from '../../../types/startup';

function position(overrides: Partial<PortfolioPosition> = {}): PortfolioPosition {
  return {
    position_id: 'position-1',
    opportunity_id: 'opportunity-1',
    company_id: 'company-1',
    ruling_id: 'ruling-1',
    status: 'active',
    entry_rationale: 'Retention held.',
    investor_confidence: 0.7,
    entered_at: '2026-07-20T12:00:00Z',
    canonical_name: 'Acme',
    legacy_startup_id: 'startup-1',
    ...overrides,
  };
}

const startups = [
  { id: 'startup-1', scout: { name: 'Acme', sector: 'Fintech', funding_stage: 'Seed' }, review: { overall_score: 7.4 } },
] as unknown as Startup[];

describe('buildPositionRows', () => {
  it('enriches a position from its legacy startup row', () => {
    const [row] = buildPositionRows([position()], startups);
    expect(row.name).toBe('Acme');
    expect(row.sector).toBe('Fintech');
    expect(row.stage).toBe('Seed');
    expect(row.score).toBe(7.4);
  });

  it('leaves enrichment null when there is no legacy bridge, without inventing values', () => {
    const [row] = buildPositionRows([position({ legacy_startup_id: null, canonical_name: 'Beta' })], startups);
    expect(row.name).toBe('Beta');
    expect(row.startupId).toBeNull();
    expect(row.sector).toBeNull();
    expect(row.score).toBeNull();
  });

  it('falls back to the canonical domain when no name exists at all', () => {
    const [row] = buildPositionRows(
      [position({ canonical_name: undefined, canonical_domain: 'gamma.io', legacy_startup_id: null })],
      startups,
    );
    expect(row.name).toBe('gamma.io');
  });
});

describe('sectorConcentration', () => {
  it('computes percentages from the rendered rows only', () => {
    const rows = buildPositionRows(
      [
        position({ position_id: 'p1' }),
        position({ position_id: 'p2', legacy_startup_id: null }),
      ],
      startups,
    );
    expect(sectorConcentration(rows)).toEqual([
      { sector: 'Fintech', count: 1, pct: 50 },
      { sector: 'Unknown', count: 1, pct: 50 },
    ]);
  });

  it('returns an empty list when there are no positions', () => {
    expect(sectorConcentration([])).toEqual([]);
  });
});
