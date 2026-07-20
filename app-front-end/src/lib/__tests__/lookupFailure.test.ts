import { describe, expect, it } from 'vitest';

import { resolveLookupFailure } from '../lookupFailure';

describe('resolveLookupFailure', () => {
  it('surfaces the lookup job failure even after a scout row has matched', () => {
    expect(
      resolveLookupFailure({
        hasMatchedStartup: true,
        memoStatus: { status: 'generating' },
        jobStatus: { failed: true, message: 'Reviewer could not complete.' },
      }),
    ).toBe('Reviewer could not complete.');
  });

  it('prefers the pipeline-state error when the memo endpoint is terminal', () => {
    expect(
      resolveLookupFailure({
        hasMatchedStartup: true,
        memoStatus: { status: 'failed', error: 'Partner persistence failed.' },
        jobStatus: { failed: true, message: 'Generic lookup failure.' },
      }),
    ).toBe('Partner persistence failed.');
  });

  it.each(['blocked', 'failed_stage'] as const)(
    'treats %s as terminal actionable failure even without the legacy failed flag',
    (status) => {
      expect(
        resolveLookupFailure({
          hasMatchedStartup: false,
          jobStatus: {
            status,
            failed: false,
            detail: 'Evaluation could not continue.',
            recovery_action: 'Correct the configuration and retry.',
          },
        }),
      ).toBe('Evaluation could not continue. Correct the configuration and retry.');
    },
  );
});
