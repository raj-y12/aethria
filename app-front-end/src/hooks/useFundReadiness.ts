/**
 * Fund readiness gate. Distinguishes a deliberately published mandate from the
 * bootstrap default, so first-run users are routed through the Fund Policy
 * Builder before they reach the deal queue.
 */
import { useQuery } from '@tanstack/react-query';
import { fetchAgentsStatus } from '../api/agents';
import type { AgentsStatus } from '../api/agents';

export interface FundReadiness {
  loading: boolean;
  /** True once the fund has published a real mandate (not the default). */
  mandatePublished: boolean;
  /** True when we could not determine readiness (treat as published to avoid lockout). */
  unknown: boolean;
  refetch: () => void;
}

export type MandatePrompt = 'unavailable' | 'missing' | 'publish' | 'ready';

export function deriveMandatePrompt({
  hasActiveThesis,
  mandatePublished,
  unknown,
}: {
  hasActiveThesis: boolean;
  mandatePublished: boolean;
  unknown: boolean;
}): MandatePrompt {
  if (unknown) return 'unavailable';
  if (mandatePublished) return 'ready';
  return hasActiveThesis ? 'publish' : 'missing';
}

export function deriveFundReadiness(
  data: Pick<AgentsStatus, 'mandate_published'> | null,
  isError: boolean,
): Pick<FundReadiness, 'mandatePublished' | 'unknown'> {
  const unknown = isError || data == null;
  return {
    mandatePublished: !unknown && data.mandate_published === true,
    unknown,
  };
}

export function useFundReadiness(): FundReadiness {
  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ['agents-status'],
    queryFn: () => fetchAgentsStatus(),
    staleTime: 30_000,
    refetchOnMount: 'always',
    placeholderData: (prev) => prev ?? undefined,
  });

  const readiness = deriveFundReadiness(data ?? null, isError);
  return {
    loading: isLoading,
    ...readiness,
    refetch: () => void refetch(),
  };
}
