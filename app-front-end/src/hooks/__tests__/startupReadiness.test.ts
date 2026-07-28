import { describe, expect, it } from 'vitest';

import { startupQueryReady } from '../useSystemData';

describe('startup query readiness', () => {
  it('does not treat placeholder data as a settled network fetch', () => {
    expect(startupQueryReady({ isFetched: false, isFetching: true })).toBe(false);
  });

  it('is ready after the first fetch has completed', () => {
    expect(startupQueryReady({ isFetched: true, isFetching: false })).toBe(true);
  });
});
