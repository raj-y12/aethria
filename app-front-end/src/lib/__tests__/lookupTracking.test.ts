import { describe, expect, it } from 'vitest';

import { findTrackedLookupStartup, lookupChipStatus } from '../lookupTracking';
import type { Startup } from '../../types/startup';

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
});

describe('findTrackedLookupStartup', () => {
  const startup = {
    id: 'existing-startup',
    scout: {
      name: 'Acme',
      origin_type: 'periodic_scout',
      lookup_id: 'older-lookup-id',
    },
  } as Startup;

  it('matches an already-known company by the terminal job startup id', () => {
    expect(
      findTrackedLookupStartup([startup], {
        lookupId: 'new-lookup-id',
        outcomeStartupId: 'existing-startup',
        isRerun: false,
      }),
    ).toBe(startup);
  });
});
