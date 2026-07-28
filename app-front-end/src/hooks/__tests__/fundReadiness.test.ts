import { describe, expect, it } from 'vitest';

import { deriveFundReadiness } from '../useFundReadiness';

describe('fund readiness', () => {
  it('does not fail open when readiness cannot be read', () => {
    expect(deriveFundReadiness(null, true)).toEqual({ mandatePublished: false, unknown: true });
  });

  it('uses the authoritative published mandate flag', () => {
    expect(deriveFundReadiness({ mandate_published: true } as never, false)).toEqual({
      mandatePublished: true,
      unknown: false,
    });
  });
});
