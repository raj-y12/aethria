import type { LookupJobStatus, MemoApiResponse } from '../api/startups';

interface LookupFailureInputs {
  hasMatchedStartup: boolean;
  memoStatus?: Pick<MemoApiResponse, 'status' | 'error'> | null;
  jobStatus?: Pick<LookupJobStatus, 'failed'> & Partial<Pick<
    LookupJobStatus,
    'status' | 'message' | 'detail' | 'recovery_action'
  >> | null;
}

function actionableStatusMessage(
  jobStatus: LookupFailureInputs['jobStatus'],
): string | undefined {
  const detail = jobStatus?.detail?.trim() || jobStatus?.message?.trim();
  const recovery = jobStatus?.recovery_action?.trim();
  if (!detail) return recovery;
  if (!recovery || detail.includes(recovery)) return detail;
  return `${detail} ${recovery}`;
}

/** Resolve terminal lookup failure across both persistence paths. */
export function resolveLookupFailure({
  hasMatchedStartup,
  memoStatus,
  jobStatus,
}: LookupFailureInputs): string | undefined {
  if (hasMatchedStartup && memoStatus?.status === 'ready') {
    return undefined;
  }
  if (hasMatchedStartup && memoStatus?.status === 'failed') {
    return memoStatus.error?.trim() || 'The lookup pipeline failed after finding the company.';
  }
  if (jobStatus?.failed) {
    return actionableStatusMessage(jobStatus) || 'Lookup failed.';
  }
  if (jobStatus?.status === 'skipped') {
    return actionableStatusMessage(jobStatus) || 'The lookup did not run.';
  }
  return undefined;
}
