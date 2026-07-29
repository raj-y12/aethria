import { describe, expect, it } from 'vitest';

import {
  findTrackedLookupStartup,
  lookupChipStatus,
  rerunHasSettled,
} from '../lookupTracking';
import type { Startup } from '../../types/startup';

const DISPATCHED_AT = '2026-07-29T12:00:00Z';

function makeStartup(overrides: Partial<Startup> = {}): Startup {
  return {
    id: 'existing-startup',
    scout: {
      name: 'Acme',
      origin_type: 'periodic_scout',
      lookup_id: 'older-lookup-id',
    },
    ...overrides,
  } as Startup;
}

describe('lookupChipStatus', () => {
  it('does not treat a preserved old partner decision as a completed rerun', () => {
    expect(
      lookupChipStatus({
        isRerun: true,
        isActive: true,
        lookupDecided: false,
        hasPartner: true,
        hasReview: true,
      }),
    ).toBe('reviewing');
  });

  it('marks the active rerun decided only from its live completion state', () => {
    expect(
      lookupChipStatus({
        isRerun: true,
        isActive: true,
        lookupDecided: true,
        hasPartner: true,
        hasReview: true,
      }),
    ).toBe('decided');
  });

  it('lets a backgrounded rerun reach decided once fresh output lands', () => {
    // Regression: a backgrounded rerun had no live poll, so it was pinned to
    // 'reviewing' forever and sat on the rail as a permanent in-flight chip.
    expect(
      lookupChipStatus({
        isRerun: true,
        isActive: false,
        lookupDecided: false,
        hasPartner: true,
        hasReview: true,
        rerunSettled: true,
      }),
    ).toBe('decided');
  });

  it('keeps a backgrounded rerun in flight until its output is fresh', () => {
    expect(
      lookupChipStatus({
        isRerun: true,
        isActive: false,
        lookupDecided: false,
        hasPartner: true,
        hasReview: true,
        rerunSettled: false,
      }),
    ).toBe('reviewing');
  });

  it('leaves plain lookup statuses unchanged', () => {
    const base = { isRerun: false, isActive: true, lookupDecided: false };
    expect(lookupChipStatus({ ...base, hasPartner: true, hasReview: true })).toBe('decided');
    expect(lookupChipStatus({ ...base, hasPartner: false, hasReview: true })).toBe('reviewing');
    expect(lookupChipStatus({ ...base, hasPartner: false, hasReview: false })).toBe('scouting');
  });
});

describe('rerunHasSettled', () => {
  it('treats output newer than the dispatch as fresh', () => {
    const startup = makeStartup({
      timestamps: { partnered_at: '2026-07-29T12:05:00Z' },
    });
    expect(rerunHasSettled({ startup, acceptedAt: DISPATCHED_AT })).toBe(true);
  });

  it('ignores output preserved from before the dispatch', () => {
    const startup = makeStartup({
      timestamps: { partnered_at: '2026-07-28T09:00:00Z', reviewed_at: '2026-07-28T08:00:00Z' },
    });
    expect(rerunHasSettled({ startup, acceptedAt: DISPATCHED_AT })).toBe(false);
  });

  it('accepts a fresh review even before a new partner decision', () => {
    const startup = makeStartup({
      timestamps: { partnered_at: '2026-07-28T09:00:00Z', reviewed_at: '2026-07-29T12:01:00Z' },
    });
    expect(rerunHasSettled({ startup, acceptedAt: DISPATCHED_AT })).toBe(true);
  });

  it('does not guess without a dispatch time or a row', () => {
    const startup = makeStartup({ timestamps: { partnered_at: '2026-07-29T12:05:00Z' } });
    expect(rerunHasSettled({ startup })).toBe(false);
    expect(rerunHasSettled({ startup: null, acceptedAt: DISPATCHED_AT })).toBe(false);
  });

  it('ignores unparseable timestamps', () => {
    const startup = makeStartup({ timestamps: { partnered_at: 'not-a-date' } });
    expect(rerunHasSettled({ startup, acceptedAt: DISPATCHED_AT })).toBe(false);
    expect(
      rerunHasSettled({
        startup: makeStartup({ timestamps: { partnered_at: '2026-07-29T12:05:00Z' } }),
        acceptedAt: 'nonsense',
      }),
    ).toBe(false);
  });
});

describe('findTrackedLookupStartup', () => {
  const startup = makeStartup();

  it('matches an already-known company by the terminal job startup id', () => {
    expect(
      findTrackedLookupStartup([startup], {
        lookupId: 'new-lookup-id',
        outcomeStartupId: 'existing-startup',
        isRerun: false,
      }),
    ).toBe(startup);
  });

  it('resolves a re-review by the row it targets', () => {
    // The stuck-dispatch regression: a re-review reuses an existing row, so the
    // fresh correlation id is not on it yet (and may never be). Resolving by the
    // recorded target is what lets the dispatch report progress, clear, and open.
    expect(
      findTrackedLookupStartup([startup], {
        lookupId: 'new-lookup-id',
        isRerun: true,
        targetStartupId: 'existing-startup',
      }),
    ).toBe(startup);
  });

  it('cannot resolve a re-review without a target or a stamped id', () => {
    // Documents exactly the state that stranded the chip on the rail.
    expect(
      findTrackedLookupStartup([startup], {
        lookupId: 'new-lookup-id',
        isRerun: true,
      }),
    ).toBeNull();
  });

  it('still resolves a re-review once the backend stamps the correlation id', () => {
    const stamped = makeStartup({
      scout: { name: 'Acme', origin_type: 'periodic_scout', lookup_id: 'new-lookup-id' },
    } as Partial<Startup>);
    expect(
      findTrackedLookupStartup([stamped], { lookupId: 'new-lookup-id', isRerun: true }),
    ).toBe(stamped);
  });

  it('prefers the recorded target over a stale correlation match', () => {
    const decoy = makeStartup({
      id: 'decoy',
      scout: { name: 'Decoy', origin_type: 'on_demand_lookup', lookup_id: 'new-lookup-id' },
    } as Partial<Startup>);
    expect(
      findTrackedLookupStartup([decoy, startup], {
        lookupId: 'new-lookup-id',
        isRerun: true,
        targetStartupId: 'existing-startup',
      }),
    ).toBe(startup);
  });

  it('falls through when the recorded target is not in the list', () => {
    expect(
      findTrackedLookupStartup([startup], {
        lookupId: 'new-lookup-id',
        isRerun: true,
        targetStartupId: 'not-loaded-yet',
      }),
    ).toBeNull();
  });

  it('still requires on-demand origin for a plain lookup', () => {
    expect(
      findTrackedLookupStartup([makeStartup({
        scout: { name: 'Acme', origin_type: 'periodic_scout', lookup_id: 'new-lookup-id' },
      } as Partial<Startup>)], {
        lookupId: 'new-lookup-id',
        isRerun: false,
      }),
    ).toBeNull();
  });
});
