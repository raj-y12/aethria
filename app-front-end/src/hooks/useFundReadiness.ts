/**
 * Fund readiness gate. Distinguishes a deliberately published mandate from the
 * bootstrap default, so first-run users are routed through the Fund Policy
 * Builder before they reach the deal queue.
 */
import { useQuery } from '@tanstack/react-query';
import { fetchAgentsStatus } from '../api/agents';

export interface FundReadiness {
  loading: boolean;
  /** True once the fund has published a real mandate (not the default). */
  mandatePublished: boolean;
  /** True when we could not determine readiness (treat as published to avoid lockout). */
  unknown: boolean;
  refetch: () => void;
}

export function useFundReadiness(): FundReadiness {
  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ['agents-status'],
    queryFn: () => fetchAgentsStatus(),
    staleTime: 30_000,
    placeholderData: (prev) => prev ?? undefined,
  });

  // If the status call fails, don't trap the user behind onboarding — let them in.
  const unknown = isError || data == null;
  return {
    loading: isLoading,
    mandatePublished: unknown ? true : Boolean(data?.mandate_published),
    unknown,
    refetch: () => void refetch(),
  };
}
