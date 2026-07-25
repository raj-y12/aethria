import { useQuery } from '@tanstack/react-query';
import { fetchOpportunities, fetchOpportunityDecisionView } from '../api/identity';

export function useOpportunities(limit = 100) {
  return useQuery({
    queryKey: ['opportunities', limit],
    queryFn: () => fetchOpportunities(limit),
    staleTime: 15_000,
  });
}

export function useOpportunityDecisionView(opportunityId: string | null) {
  return useQuery({
    queryKey: ['opportunity-decision-view', opportunityId],
    queryFn: () => fetchOpportunityDecisionView(opportunityId as string),
    enabled: Boolean(opportunityId),
    staleTime: 15_000,
  });
}
