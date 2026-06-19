import { useEffect, useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { openStartupsStream } from '../api/stream';

/**
 * Subscribe to the backend SSE stream and refetch deal-flow the moment the
 * pipeline writes new data, instead of waiting for a poll tick.
 *
 * Returns whether the stream is currently connected so callers can relax their
 * polling to a slow backstop while push is healthy, and fall back to brisk
 * polling when it is not. The stream is only opened while `enabled` (e.g. the
 * tab is visible) to bound open connections and avoid pushing to hidden tabs.
 */
export function useStartupsStream(enabled: boolean): boolean {
  const queryClient = useQueryClient();
  const [connected, setConnected] = useState(false);

  useEffect(() => {
    if (!enabled) {
      setConnected(false);
      return;
    }

    const handle = openStartupsStream(
      (event) => {
        if (event.type !== 'startups_changed') return;
        // Nudge model: invalidate, let the existing typed query refetch.
        // Escalations come out of the partner stage, so refresh them too.
        void queryClient.invalidateQueries({ queryKey: ['startups', 'list'] });
        void queryClient.invalidateQueries({ queryKey: ['escalations'] });
      },
      (status) => setConnected(status === 'open'),
    );

    return () => {
      handle.close();
      setConnected(false);
    };
  }, [enabled, queryClient]);

  return connected;
}
