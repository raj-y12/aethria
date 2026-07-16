import { apiRequest, encodedId } from './client';

export type JobStatus =
  | 'accepted'
  | 'running'
  | 'retry_wait'
  | 'blocked'
  | 'succeeded'
  | 'failed'
  | 'dead_letter'
  | 'cancelled';

export interface DurableJob {
  job_id: string;
  job_type: string;
  status: JobStatus;
  attempts: number;
  max_attempts: number;
  pipeline_run_id: string;
  lookup_id?: string | null;
  accepted_at: string;
  started_at?: string | null;
  completed_at?: string | null;
  next_attempt_at: string;
  error?: string | null;
  block_code?: string | null;
  recovery_action?: string | null;
}

export async function fetchJobs(status?: JobStatus[], limit = 50): Promise<DurableJob[]> {
  const params = new URLSearchParams({ limit: String(limit) });
  if (status?.length) params.set('status', status.join(','));
  const result = await apiRequest<{ jobs?: DurableJob[] }>(`/api/jobs?${params}`);
  return Array.isArray(result.jobs) ? result.jobs : [];
}

export function fetchJob(jobId: string): Promise<DurableJob> {
  return apiRequest(`/api/jobs/${encodedId(jobId, 'jobId')}`);
}

export function retryJob(jobId: string): Promise<DurableJob> {
  return apiRequest(`/api/jobs/${encodedId(jobId, 'jobId')}/retry`, { method: 'POST' });
}

export function cancelJob(jobId: string): Promise<DurableJob> {
  return apiRequest(`/api/jobs/${encodedId(jobId, 'jobId')}/cancel`, { method: 'POST' });
}

export function isJobTerminal(status: JobStatus): boolean {
  return ['succeeded', 'failed', 'dead_letter', 'cancelled'].includes(status);
}

