import { useQuery } from '@tanstack/react-query';
import { fetchPortfolioPositions } from '../api/portfolio';

export function usePortfolioPositions(limit = 100) {
  return useQuery({
    queryKey: ['portfolio-positions', limit],
    queryFn: () => fetchPortfolioPositions(limit),
    staleTime: 30_000,
  });
}
