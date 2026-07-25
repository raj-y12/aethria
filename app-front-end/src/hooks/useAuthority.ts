import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  getAuthorityStatus,
  rollbackAuthority,
  transitionAuthority,
  type AuthorityStatus,
  type RollbackAuthorityInput,
  type TransitionAuthorityInput,
} from '../api/authority';

export const authorityStatusQueryKey = ['authority', 'status'] as const;

async function invalidateAuthorityDependentQueries(queryClient: ReturnType<typeof useQueryClient>) {
  await Promise.all([
    queryClient.invalidateQueries({ queryKey: authorityStatusQueryKey }),
    queryClient.invalidateQueries({ queryKey: ['system', 'status'] }),
    queryClient.invalidateQueries({ queryKey: ['startups'] }),
    queryClient.invalidateQueries({ queryKey: ['escalations'] }),
    queryClient.invalidateQueries({ queryKey: ['institutional', 'opportunity'] }),
  ]);
}

function blockedReasonFor(status: AuthorityStatus | null): string | null {
  if (!status) return null;
  if (status.kill_switch) {
    return 'Authority rollback is active. Restore green reconciliation before re-arming canonical operations.';
  }
  if (status.mode === 'canonical_read' && !status.canonical_reads_allowed) {
    return 'Canonical read is blocked until reconciliation is green.';
  }
  return null;
}

export function useAuthority() {
  const query = useQuery({
    queryKey: authorityStatusQueryKey,
    queryFn: getAuthorityStatus,
    staleTime: 15_000,
    retry: 1,
  });
  const status = query.data ?? null;

  return {
    status,
    isCanonicalRead: Boolean(status?.mode === 'canonical_read' && status.canonical_reads_allowed),
    isCanonicalWrite: Boolean(status?.mode === 'canonical_write' && status.canonical_writes_allowed),
    blockedReason: blockedReasonFor(status),
    refetch: query.refetch,
  };
}

export function useTransitionAuthority() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: TransitionAuthorityInput) => transitionAuthority(input),
    onSuccess: () => invalidateAuthorityDependentQueries(queryClient),
  });
}

export function useRollbackAuthority() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: RollbackAuthorityInput) => rollbackAuthority(input),
    onSuccess: () => invalidateAuthorityDependentQueries(queryClient),
  });
}
