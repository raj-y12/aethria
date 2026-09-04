import type { PortfolioPosition } from '../../api/portfolio';
import type { Startup } from '../../types/startup';

export interface PositionRow {
  position: PortfolioPosition;
  name: string;
  startupId: string | null;
  sector: string | null;
  stage: string | null;
  score: number | null;
}

/* Positions are authoritative for what we hold. Sector and stage are
 * display-only enrichment from the legacy startup row; score stays unavailable
 * until this table is backed by canonical evaluation projection. */
export function buildPositionRows(positions: PortfolioPosition[], startups: Startup[]): PositionRow[] {
  const byId = new Map(startups.map((s) => [s.id, s]));
  return positions.map((position) => {
    const startupId = position.legacy_startup_id ?? null;
    const legacy = startupId ? byId.get(startupId) : undefined;
    return {
      position,
      name: position.canonical_name || legacy?.scout?.name || position.canonical_domain || 'Unknown',
      startupId,
      sector: legacy?.scout?.sector || null,
      stage: legacy?.scout?.funding_stage || null,
      score: null,
    };
  });
}

/* Derived from the rows actually on screen, so the bars can never contradict
 * the list above them (the old precomputed analytics doc could). */
export function sectorConcentration(rows: PositionRow[]): { sector: string; count: number; pct: number }[] {
  if (rows.length === 0) return [];
  const counts = new Map<string, number>();
  for (const row of rows) {
    const key = row.sector ?? 'Unknown';
    counts.set(key, (counts.get(key) ?? 0) + 1);
  }
  return [...counts.entries()]
    .map(([sector, count]) => ({ sector, count, pct: Math.round((count / rows.length) * 100) }))
    .sort((a, b) => b.count - a.count || a.sector.localeCompare(b.sector));
}
