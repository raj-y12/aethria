import { describe, expect, it } from 'vitest';

import { lookupChipStatus } from '../lookupTracking';

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
