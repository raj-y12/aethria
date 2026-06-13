import { useCallback } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { acknowledgeStartup } from '../api/startups';
import type { Startup } from '../types/startup';

/**
 * Optimistically marks a startup as seen/acknowledged and syncs the server
 * response back into the list + detail caches. Shared by the Flow workspace
 * (row clicks) and Dispatch (opening a lookup result memo).
 */
export function useAcknowledgeStartup(
  onSynced?: (updated: Startup) => void,
): (startup: Startup) => Startup {
  const queryClient = useQueryClient();

  return useCallback(
    (startup: Startup) => {
      const now = new Date().toISOString();
      const optimistic: Startup = {
        ...startup,
        is_new_to_user: false,
        timestamps: {
          ...(startup.timestamps ?? {}),
          acknowledged_at: startup.timestamps?.acknowledged_at ?? now,
          last_seen_by_user_at: now,
        },
      };
      queryClient.setQueryData<Startup[]>(['startups', 'list'], (prev) =>
        prev?.map((s) => (s.id === startup.id ? { ...s, ...optimistic } : s)) ?? prev,
      );
      queryClient.setQueryData<Startup | null>(['startup', 'detail', startup.id], (prev) =>
        prev ? { ...prev, ...optimistic } : prev,
      );
      void acknowledgeStartup(startup.id).then((updated) => {
        if (!updated) return;
        queryClient.setQueryData<Startup[]>(['startups', 'list'], (prev) =>
          prev?.map((s) => (s.id === updated.id ? { ...s, ...updated } : s)) ?? prev,
        );
        queryClient.setQueryData<Startup | null>(['startup', 'detail', updated.id], updated);
        onSynced?.(updated);
      });
      return optimistic;
    },
    [queryClient, onSynced],
  );
}
