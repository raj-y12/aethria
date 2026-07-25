import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { act, renderHook, waitFor } from '@testing-library/react';
import type { ReactNode } from 'react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const api = vi.hoisted(() => ({
  getAuthorityStatus: vi.fn(),
  transitionAuthority: vi.fn(),
  rollbackAuthority: vi.fn(),
}));

vi.mock('../api/authority', () => api);

import { useAuthority, useRollbackAuthority } from './useAuthority';

function wrapper(queryClient: QueryClient) {
  return ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  );
}

function createQueryClient() {
  return new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
}

describe('useAuthority', () => {
  beforeEach(() => {
    api.getAuthorityStatus.mockReset();
    api.transitionAuthority.mockReset();
    api.rollbackAuthority.mockReset();
  });

  it('keeps a canonical-read authority status visible without consulting legacy startup state', async () => {
    api.getAuthorityStatus.mockResolvedValue({
      mode: 'canonical_read',
      version: 4,
      kill_switch: false,
      canonical_writes_allowed: false,
      canonical_reads_allowed: true,
      last_reconciliation_status: 'green',
    });
    const queryClient = createQueryClient();
    queryClient.setQueryData(['institutional', 'opportunity', 'opportunity-1'], {
      decision_state: 'blocked',
      block_recovery: 'Resolve identity before evaluation.',
    });

    const { result } = renderHook(() => useAuthority(), { wrapper: wrapper(queryClient) });

    await waitFor(() => expect(result.current.isCanonicalRead).toBe(true));
    expect(result.current.status?.mode).toBe('canonical_read');
    expect(queryClient.getQueryData(['institutional', 'opportunity', 'opportunity-1'])).toEqual({
      decision_state: 'blocked',
      block_recovery: 'Resolve identity before evaluation.',
    });
  });

  it('exposes explicit rollback recovery detail', async () => {
    api.getAuthorityStatus.mockResolvedValue({
      mode: 'legacy',
      version: 5,
      kill_switch: true,
      canonical_writes_allowed: false,
      canonical_reads_allowed: false,
      last_reconciliation_status: 'pending',
    });

    const { result } = renderHook(() => useAuthority(), { wrapper: wrapper(createQueryClient()) });

    await waitFor(() => expect(result.current.blockedReason).toContain('rollback'));
    expect(result.current.blockedReason).toContain('green reconciliation');
  });

  it('invalidates authority, status, startup, escalation, and opportunity queries after rollback', async () => {
    api.getAuthorityStatus.mockResolvedValue({
      mode: 'canonical_write',
      version: 4,
      kill_switch: false,
      canonical_writes_allowed: true,
      canonical_reads_allowed: false,
      last_reconciliation_status: 'green',
    });
    api.rollbackAuthority.mockResolvedValue({
      mode: 'legacy',
      version: 5,
      kill_switch: true,
      canonical_writes_allowed: false,
      canonical_reads_allowed: false,
      last_reconciliation_status: 'pending',
    });
    const queryClient = createQueryClient();
    const invalidate = vi.spyOn(queryClient, 'invalidateQueries');
    const { result } = renderHook(() => useRollbackAuthority(), { wrapper: wrapper(queryClient) });

    await act(async () => {
      await result.current.mutateAsync({ expected_version: 4, reason: 'Reconciliation mismatch' });
    });

    expect(invalidate).toHaveBeenCalledWith({ queryKey: ['authority', 'status'] });
    expect(invalidate).toHaveBeenCalledWith({ queryKey: ['system', 'status'] });
    expect(invalidate).toHaveBeenCalledWith({ queryKey: ['startups'] });
    expect(invalidate).toHaveBeenCalledWith({ queryKey: ['escalations'] });
    expect(invalidate).toHaveBeenCalledWith({ queryKey: ['institutional', 'opportunity'] });
  });
});
