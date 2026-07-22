import { describe, expect, it, vi } from 'vitest';

import type { DurableJob } from '../../api/jobs';
import { supersedeLookupRetryQueries } from '../lookupRetrySupersession';

describe('supersedeLookupRetryQueries', () => {
  it('replaces an old terminal attempt and invalidates/refetches both authorities', async () => {
    const setQueryData = vi.fn();
    const invalidateQueries = vi.fn().mockResolvedValue(undefined);
    const refetchDurableJob = vi.fn().mockResolvedValue(undefined);
    const refetchLookupStatus = vi.fn().mockResolvedValue(undefined);
    const job: DurableJob = {
      job_id: 'job-1',
      job_type: 'company_lookup',
      status: 'accepted',
      attempts: 3,
      max_attempts: 4,
      pipeline_run_id: 'pipeline-1',
      lookup_id: 'lookup-1',
      accepted_at: '2026-07-21T12:00:00Z',
      next_attempt_at: '2026-07-21T12:00:00Z',
    };

    await supersedeLookupRetryQueries({
      queryClient: { setQueryData, invalidateQueries },
      job,
      lookupId: 'lookup-1',
      refetchDurableJob,
      refetchLookupStatus,
    });

    expect(setQueryData).toHaveBeenCalledWith(
      ['startups', 'lookup-status', 'lookup-1'],
      expect.objectContaining({
        status: 'accepted',
        terminal: false,
        failed: false,
        attempt: 4,
        disposition: 'accepted',
      }),
    );
    expect(invalidateQueries).toHaveBeenCalledWith({
      queryKey: ['jobs', 'detail', 'job-1'],
      refetchType: 'none',
    });
    expect(invalidateQueries).toHaveBeenCalledWith({
      queryKey: ['startups', 'lookup-status', 'lookup-1'],
      refetchType: 'none',
    });
    expect(refetchDurableJob).toHaveBeenCalledOnce();
    expect(refetchLookupStatus).toHaveBeenCalledOnce();
  });
});
