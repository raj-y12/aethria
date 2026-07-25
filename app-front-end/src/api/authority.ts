import { authedFetch } from './auth';

const API_BASE =
  typeof window !== 'undefined' ? (import.meta.env.VITE_API_URL ?? '') : 'http://localhost:8000';

export type RolloutMode =
  | 'legacy'
  | 'shadow'
  | 'backfill'
  | 'canonical_write'
  | 'canonical_read';

export interface AuthorityStatus {
  mode: RolloutMode;
  version: number;
  kill_switch: boolean;
  canonical_writes_allowed: boolean;
  canonical_reads_allowed: boolean;
  last_reconciliation_status: string | null;
}

export interface RolloutRecord {
  user_id: string;
  mode: RolloutMode;
  version: number;
  activated_at?: string | null;
  activated_by?: string | null;
  snapshot_id?: string | null;
  last_reconciliation_status?: string | null;
  kill_switch: boolean;
  created_at?: string;
  updated_at?: string;
}

export interface TransitionAuthorityInput {
  target_mode: RolloutMode;
  expected_version: number;
  snapshot_id?: string | null;
}

export interface RollbackAuthorityInput {
  expected_version: number;
  reason: string;
}

function requireExpectedVersion(input: { expected_version?: unknown }): void {
  if (!Number.isInteger(input.expected_version) || Number(input.expected_version) < 0) {
    throw new Error('expected_version is required and must be a non-negative integer');
  }
}

async function authorityRequest<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await authedFetch(`${API_BASE}${path}`, {
    ...init,
    headers: { Accept: 'application/json', ...init?.headers },
  });
  if (!response.ok) throw new Error(await response.text());
  return (await response.json()) as T;
}

export function getAuthorityStatus(): Promise<AuthorityStatus> {
  return authorityRequest<AuthorityStatus>('/api/authority/status');
}

export async function transitionAuthority(input: TransitionAuthorityInput): Promise<RolloutRecord> {
  requireExpectedVersion(input);
  return await authorityRequest<RolloutRecord>('/api/authority/transition', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(input),
  });
}

export async function rollbackAuthority(input: RollbackAuthorityInput): Promise<RolloutRecord> {
  requireExpectedVersion(input);
  if (!input.reason?.trim()) throw new Error('rollback reason is required');
  return await authorityRequest<RolloutRecord>('/api/authority/rollback', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(input),
  });
}
