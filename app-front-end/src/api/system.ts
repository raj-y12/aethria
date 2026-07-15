import { apiRequest } from './client';

export interface DurableExecutionStatus {
  required: boolean;
  ready: boolean;
  error: string | null;
  counts: Record<string, number>;
}

export interface SystemStatus {
  status: string;
  durable_jobs: DurableExecutionStatus;
}

export function fetchSystemStatus(): Promise<SystemStatus> {
  return apiRequest('/api/system/status');
}
