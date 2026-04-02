import { useState, useEffect, useRef, useCallback } from 'react';
import { QUERY_LIVE_IDLE_MS } from '../lib/queryIntent';

/**
 * Drives LIVE / SEMI_DYNAMIC polling: no background refetch when tab hidden or user idle.
 */
export function useQueryLiveGate() {
  const [tabVisible, setTabVisible] = useState(() =>
    typeof document === 'undefined' ? true : document.visibilityState === 'visible'
  );
  const lastActivityRef = useRef(Date.now());
  const [, tick] = useState(0);

  const bumpActivity = useCallback(() => {
    lastActivityRef.current = Date.now();
    tick((n) => n + 1);
  }, []);

  useEffect(() => {
    if (typeof document === 'undefined') return;
    const onVis = () => {
      setTabVisible(document.visibilityState === 'visible');
      if (document.visibilityState === 'visible') bumpActivity();
    };
    document.addEventListener('visibilitychange', onVis);
    return () => document.removeEventListener('visibilitychange', onVis);
  }, [bumpActivity]);

  useEffect(() => {
    if (typeof window === 'undefined') return;
    const opts = { passive: true } as AddEventListenerOptions;
    const onActivity = () => bumpActivity();
    window.addEventListener('pointerdown', onActivity, opts);
    window.addEventListener('keydown', onActivity);
    window.addEventListener('wheel', onActivity, opts);
    return () => {
      window.removeEventListener('pointerdown', onActivity);
      window.removeEventListener('keydown', onActivity);
      window.removeEventListener('wheel', onActivity);
    };
  }, [bumpActivity]);

  const [userActive, setUserActive] = useState(true);
  useEffect(() => {
    if (typeof window === 'undefined') return;
    const id = window.setInterval(() => {
      setUserActive(Date.now() - lastActivityRef.current < QUERY_LIVE_IDLE_MS);
    }, 5_000);
    return () => window.clearInterval(id);
  }, []);

  return { tabVisible, userActive, bumpActivity };
}
