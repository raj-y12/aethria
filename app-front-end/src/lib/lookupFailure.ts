import type { LookupJobStatus, MemoApiResponse } from '../api/startups';

interface LookupFailureInputs {
  hasMatchedStartup: boolean;
  memoStatus?: Pick<MemoApiResponse, 'status' | 'error'> | null;
  jobStatus?: Pick<LookupJobStatus, 'failed' | 'message'> | null;
}

/** Resolve terminal lookup failure across both persistence paths. */
export function resolveLookupFailure({
  hasMatchedStartup,
  memoStatus,
  jobStatus,
}: LookupFailureInputs): string | undefined {
  if (hasMatchedStartup && memoStatus?.status === 'failed') {
    return memoStatus.error?.trim() || 'The lookup pipeline failed after finding the company.';
  }
  if (jobStatus?.failed) {
    return jobStatus.message?.trim() || 'Lookup failed.';
  }
  return undefined;
}
