import { useQuery } from '@tanstack/react-query';
import {
  fetchCounterfactualProposals,
  fetchFundHypotheses,
  fetchFundObservations,
  fetchFundReplayPreview,
  type CounterfactualProposal,
  type FundHypothesis,
  type FundObservation,
  type FundReplayPreview,
} from '../api/fundIntelligence';
import { getQueryConfig } from '../lib/queryIntent';

export interface FundIntelligenceData {
  observations: FundObservation[];
  hypotheses: FundHypothesis[];
  proposals: CounterfactualProposal[];
  observationsLoading: boolean;
  hypothesesLoading: boolean;
  observationsError: boolean;
  hypothesesError: boolean;
  retryObservations: () => void;
  retryHypotheses: () => void;
}

export function useFundIntelligence(enabled = true): FundIntelligenceData {
  const observationsQuery = useQuery({
    queryKey: ['fund-intelligence', 'observations'],
    queryFn: () => fetchFundObservations(),
    ...getQueryConfig('SEMI_DYNAMIC', { pollIntervalMs: 120_000 }),
    enabled,
    placeholderData: (previous) => previous ?? [],
  });
  const hypothesesQuery = useQuery({
    queryKey: ['fund-intelligence', 'hypotheses'],
    queryFn: () => fetchFundHypotheses(),
    ...getQueryConfig('SEMI_DYNAMIC', { pollIntervalMs: 120_000 }),
    enabled,
    placeholderData: (previous) => previous ?? [],
  });
  const proposalsQuery = useQuery({
    queryKey: ['fund-intelligence', 'counterfactual-proposals'],
    queryFn: () => fetchCounterfactualProposals(),
    ...getQueryConfig('SEMI_DYNAMIC', { pollIntervalMs: 120_000 }),
    enabled,
    placeholderData: (previous) => previous ?? [],
  });

  return {
    observations: observationsQuery.data ?? [],
    hypotheses: hypothesesQuery.data ?? [],
    proposals: proposalsQuery.data ?? [],
    observationsLoading: observationsQuery.isPending,
    hypothesesLoading: hypothesesQuery.isPending,
    observationsError: observationsQuery.isError,
    hypothesesError: hypothesesQuery.isError,
    retryObservations: () => { void observationsQuery.refetch(); },
    retryHypotheses: () => { void Promise.all([hypothesesQuery.refetch(), proposalsQuery.refetch()]); },
  };
}

export function useFundReplayPreview(hypothesisId: string | null): {
  data: FundReplayPreview | undefined;
  isLoading: boolean;
  isError: boolean;
} {
  const query = useQuery({
    queryKey: ['fund-intelligence', 'replay', hypothesisId],
    queryFn: () => fetchFundReplayPreview(hypothesisId as string),
    ...getQueryConfig('STATIC'),
    enabled: Boolean(hypothesisId),
  });
  return { data: query.data, isLoading: query.isPending, isError: query.isError };
}
