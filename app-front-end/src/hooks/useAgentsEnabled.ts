/**
 * Shared hook: returns true if any agent stage is currently enabled
 * (scouts_enabled OR reviewers_enabled OR partners_enabled).
 *
 * Reads from the React Query cache so it stays in sync with
 * the live settings without additional network requests.
 */
import { useQuery } from '@tanstack/react-query';
import { fetchSettings } from '../api/settings';

export function useAgentsEnabled(): boolean {
  const { data: settings } = useQuery({
    queryKey: ['settings'],
    queryFn: () => fetchSettings().catch(() => null),
    staleTime: 30_000,
    placeholderData: (prev) => prev ?? null,
  });
  const ac = settings?.agent_config;
  return !!(ac?.scouts_enabled || ac?.reviewers_enabled || ac?.partners_enabled);
}
