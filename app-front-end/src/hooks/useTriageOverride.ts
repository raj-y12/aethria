import { useCallback, useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { triageOverride, type TriageOverrideStage } from '../api/startups';

/**
 * Fires the manual "review it anyway" / "decide it anyway" triage-funnel
 * override, then invalidates the startup's cached list/detail entries so
 * the next read picks up the freshly-written review/decision.
 */
export function useTriageOverride() {
  const queryClient = useQueryClient();
  const [pendingId, setPendingId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const run = useCallback(
    async (startupId: string, stage: TriageOverrideStage) => {
      setPendingId(startupId);
      setError(null);
      try {
        const ok = await triageOverride(startupId, stage);
        if (!ok) {
          setError(`Could not ${stage} this startup right now. Try again in a moment.`);
          return false;
        }
        await queryClient.invalidateQueries({ queryKey: ['startups', 'list'] });
        await queryClient.invalidateQueries({ queryKey: ['startup', 'detail', startupId] });
        return true;
      } catch {
        setError(`Could not ${stage} this startup right now. Try again in a moment.`);
        return false;
      } finally {
        setPendingId(null);
      }
    },
    [queryClient],
  );

  return { run, pendingId, error };
}
