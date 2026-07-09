import { useEffect, useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { openStartupsStream } from '../api/stream';

/**
 * Subscribe to the backend SSE stream and refetch deal-flow the moment the
 * pipeline writes new data, instead of waiting for a poll tick.
 *
 * Returns whether the stream is currently HEALTHY — meaning the server's hello
 * frame has actually been parsed, not merely that an HTTP 200 arrived (a proxy
 * can hold a 200 open while buffering frames). Callers relax polling to a slow
 * backstop only while push is proven healthy, and fall back to brisk polling
 * when it is connecting, stale, or closed. The stream is only opened while
 * `enabled` (e.g. the tab is visible) to bound open connections.
 */
export function useStartupsStream(enabled: boolean): boolean {
  const queryClient = useQueryClient();
  const [healthy, setHealthy] = useState(false);

  useEffect(() => {
    if (!enabled) {
      setHealthy(false);
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
      (status) => setHealthy(status === 'healthy'),
    );

    return () => {
      handle.close();
      setHealthy(false);
    };
  }, [enabled, queryClient]);

  return healthy;
}
