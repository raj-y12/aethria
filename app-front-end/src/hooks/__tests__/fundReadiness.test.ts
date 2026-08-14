import { describe, expect, it } from 'vitest';

import { deriveFundReadiness, deriveMandatePrompt } from '../useFundReadiness';

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

  it('distinguishes an existing unpublished thesis from a missing thesis', () => {
    expect(deriveMandatePrompt({ hasActiveThesis: true, mandatePublished: false, unknown: false })).toBe('publish');
    expect(deriveMandatePrompt({ hasActiveThesis: false, mandatePublished: false, unknown: false })).toBe('missing');
  });
});
