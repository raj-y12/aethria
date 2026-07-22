import type { DurableJob } from '../api/jobs';
import type { LookupJobStatus } from '../api/startups';

interface RetryQueryClient {
  setQueryData: (queryKey: readonly unknown[], data: unknown) => unknown;
  invalidateQueries: (filters: {
    queryKey: readonly unknown[];
    refetchType: 'none';
  }) => Promise<unknown>;
}

interface LookupRetrySupersessionOptions {
  queryClient: RetryQueryClient;
  job: DurableJob;
  lookupId: string;
  refetchDurableJob: () => Promise<unknown>;
  refetchLookupStatus: () => Promise<unknown>;
}

/**
 * Replace a cached terminal attempt immediately, then refresh both durable
 * authorities. The retry API has already persisted this next accepted attempt
 * before returning, so the status refetch cannot legitimately resurrect the
 * older terminal row.
 */
export async function supersedeLookupRetryQueries({
  queryClient,
  job,
  lookupId,
  refetchDurableJob,
  refetchLookupStatus,
}: LookupRetrySupersessionOptions): Promise<void> {
  const durableKey = ['jobs', 'detail', job.job_id] as const;
  const lookupKey = ['startups', 'lookup-status', lookupId] as const;
  const accepted: LookupJobStatus = {
    lookup_id: lookupId,
    job_id: job.job_id,
    pipeline_run_id: job.pipeline_run_id,
    attempt: Math.max(1, job.attempts + 1),
    disposition: 'accepted',
    status: 'accepted',
    terminal: false,
    failed: false,
  };

  queryClient.setQueryData(lookupKey, accepted);
  await Promise.all([
    queryClient.invalidateQueries({ queryKey: durableKey, refetchType: 'none' }),
    queryClient.invalidateQueries({ queryKey: lookupKey, refetchType: 'none' }),
  ]);
  await Promise.all([refetchDurableJob(), refetchLookupStatus()]);
}
