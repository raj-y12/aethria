import { useQuery } from '@tanstack/react-query';
import { fetchOutcomeCoverage } from '../api/channelsOutcomes';

export function useOutcomeCoverage() {
  return useQuery({
    queryKey: ['outcomes', 'coverage'],
    queryFn: fetchOutcomeCoverage,
    staleTime: 60_000,
    retry: false,
  });
}
