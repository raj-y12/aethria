import type { Startup } from '../types/startup';

export interface MemoTag {
  label: string;
  kind: 'sector' | 'stage' | 'origin';
}

/** Classification tags shared by the memo masthead and the IC pack PDF header:
 *  sector → stage → LOOKUP origin. Lives in lib (not memoContentHelpers) so the
 *  PDF builder can use it without a component↔lib import cycle. */
export function buildMemoTags(startup: Startup): MemoTag[] {
  const tags: MemoTag[] = [];
  const push = (value: unknown, kind: MemoTag['kind']) => {
    const label = String(value ?? '')
      .replace(/\s+/g, ' ')
      .trim()
      .replace(/_/g, ' ')
      .toUpperCase();
    if (!label || tags.some((tag) => tag.label === label)) return;
    tags.push({ label, kind });
  };
  push(startup.scout.sector, 'sector');
  push(startup.scout.funding_stage || startup.scout.scout_type, 'stage');
  if ((startup.scout.origin_type ?? '').toLowerCase() === 'on_demand_lookup') {
    push('LOOKUP', 'origin');
  }
  return tags;
}
