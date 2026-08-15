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

  it('keeps a matched review accessible when its memo is ready despite partner failure', () => {
    expect(
      resolveLookupFailure({
        hasMatchedStartup: true,
        memoStatus: { status: 'ready' },
        jobStatus: { failed: true, message: 'Partner could not complete.' },
      }),
    ).toBeUndefined();
  });

  it.each(['blocked', 'failed_stage'] as const)(
    'does not surface %s as terminal when the attempt is explicitly retryable',
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
      ).toBeUndefined();
    },
  );
});

describe('an unreachable status endpoint is not a failed lookup', () => {
  it('keeps the dispatch alive when the status check itself could not complete', () => {
    // A 500 on /lookup-status used to be mapped to failed+terminal, so the
    // analyst saw "dispatch failed" and then the finished memo appeared.
    expect(
      resolveLookupFailure({
        hasMatchedStartup: true,
        memoStatus: { status: 'generating' },
        jobStatus: {
          failed: false,
          status: 'pending',
          detail: 'Could not verify lookup status; still checking.',
        },
      }),
    ).toBeUndefined();
  });
});
