import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useAuth } from '@clerk/react-router';
import {
  cancelOnDemandLookups,
  queueOnDemandLookup,
  fetchStartupDetail,
  fetchLookupJobStatus,
} from '../api/startups';
import { getQueryConfig, type QueryLiveGate } from '../lib/queryIntent';
import { buildLookupSnapshotProps } from '../lib/productChromeMappers';
import {
  getDispatchLookupStorageKey,
  loadDispatchLookupSnapshot,
  saveDispatchLookupSnapshot,
  type PersistedDispatchLookup,
} from '../lib/dispatchLookupPersistence';
import type { Startup } from '../types/startup';
import type { FundConfiguration } from '../lib/fundConfiguration';
import type { LookupChip, LookupProgress } from '../components/DispatchCommandBar';

type TrackedLookup = PersistedDispatchLookup;

export type LookupPhaseLabel = 'Scouting' | 'Reviewing' | 'Deciding' | null;

interface UseDispatchLookupOptions {
  startups: Startup[];
  liveGate: QueryLiveGate;
  fundConfiguration?: FundConfiguration;
  /** Invoked when the analyst opens a finished lookup's memo (navigate + acknowledge). */
  onOpenMemo: (startup: Startup) => void;
}

/**
 * The Dispatch lookup machinery — extracted from the old MainLayout so the
 * ⌘K command surface is owned by the app frame and available from every
 * workspace. The DispatchCommandBar itself is unchanged; this hook only
 * relocates its state.
 */
export function useDispatchLookup({
  startups,
  liveGate,
  fundConfiguration,
  onOpenMemo,
}: UseDispatchLookupOptions) {
  const { userId } = useAuth();
  const queryClient = useQueryClient();

  const [commandBarOpen, setCommandBarOpen] = useState(false);
  const [input, setInput] = useState('');
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [pendingLookup, setPendingLookup] = useState<TrackedLookup | null>(null);
  const [hydratedStorageKey, setHydratedStorageKey] = useState<string | null>(null);
  // Other in-flight lookups the analyst started via "Look up another". The active
  // one (pendingLookup) keeps the full polling machinery; these are chips that can
  // be focused (swapped into active) and read their status from the startups list.
  const [backgroundLookups, setBackgroundLookups] = useState<TrackedLookup[]>([]);
  const requestSeqRef = useRef(0);

  const storageKey = useMemo(() => getDispatchLookupStorageKey(userId), [userId]);

  const submit = useCallback(async () => {
    const value = input.trim();
    // Allow starting a new lookup even while one is tracked ("Look up another"):
    // the prior keeps running server-side and lands in the queue. Only block
    // while a submit is mid-flight.
    if (!value || busy) return;
    const requestSeq = requestSeqRef.current + 1;
    requestSeqRef.current = requestSeq;
    setBusy(true);
    setMessage('Submitting lookup request...');
    try {
      const lookupId = crypto.randomUUID();
      const queued = await queueOnDemandLookup(value, lookupId);
      if (requestSeqRef.current !== requestSeq) return;
      // Background the lookup currently in focus so it survives as a chip.
      const current = pendingLookup;
      if (current && !current.autoOpened && current.lookupId !== queued.lookupId) {
        setBackgroundLookups((bg) => [current, ...bg.filter((l) => l.lookupId !== current.lookupId)]);
      }
      setPendingLookup({
        lookupId: queued.lookupId,
        queryLabel: value,
        autoOpened: false,
      });
      setMessage(
        `Lookup queued for ${queued.companyName}. We are now finding and validating the company profile.`,
      );
      setInput('');
    } catch {
      setMessage('Could not submit lookup request. Please retry in a few seconds.');
    } finally {
      if (requestSeqRef.current === requestSeq) setBusy(false);
    }
  }, [input, busy, pendingLookup]);

  const cancel = useCallback(() => {
    const lookupIds = [
      pendingLookup?.lookupId,
      ...backgroundLookups.map((lookup) => lookup.lookupId),
    ].filter((id): id is string => Boolean(id?.trim()));
    requestSeqRef.current += 1;
    setBusy(false);
    setPendingLookup(null);
    setBackgroundLookups([]);
    setMessage(null);
    setInput('');
    setCommandBarOpen(false);
    if (storageKey && typeof window !== 'undefined') {
      window.localStorage.removeItem(storageKey);
    }
    void cancelOnDemandLookups(lookupIds);
  }, [backgroundLookups, storageKey, pendingLookup]);

  useEffect(() => {
    if (!storageKey || hydratedStorageKey === storageKey) return;
    const restored = loadDispatchLookupSnapshot(window.localStorage, storageKey);
    setPendingLookup(restored.pendingLookup);
    setBackgroundLookups(restored.backgroundLookups);
    setHydratedStorageKey(storageKey);
  }, [storageKey, hydratedStorageKey]);

  useEffect(() => {
    if (!storageKey || hydratedStorageKey !== storageKey) return;
    saveDispatchLookupSnapshot(window.localStorage, storageKey, {
      pendingLookup,
      backgroundLookups,
    });
  }, [backgroundLookups, storageKey, hydratedStorageKey, pendingLookup]);

  const pendingLookupMatch = useMemo(() => {
    if (!pendingLookup) return null;
    const id = pendingLookup.lookupId.trim();
    if (!id) return null;
    return (
      startups.find((s) => {
        if ((s.scout.origin_type ?? '').toLowerCase() !== 'on_demand_lookup') return false;
        return (s.scout.lookup_id ?? '').trim() === id;
      }) ?? null
    );
  }, [startups, pendingLookup]);

  const lookupFailureQuery = useQuery({
    queryKey: ['startups', 'lookup-status', pendingLookup?.lookupId ?? ''],
    queryFn: () => fetchLookupJobStatus(pendingLookup!.lookupId),
    enabled: Boolean(
      pendingLookup && !pendingLookupMatch && pendingLookup.lookupId.trim().length > 0,
    ),
    staleTime: 4_000,
    refetchInterval: (q) => {
      if (!liveGate.tabVisible || !liveGate.userActive) return false;
      const row = q.state.data as { failed?: boolean } | undefined;
      if (row?.failed) return false;
      return 8_000;
    },
    retry: 1,
  });

  useEffect(() => {
    if (!pendingLookup || pendingLookupMatch) return;
    const row = lookupFailureQuery.data;
    if (!row?.failed) return;
    setMessage(
      row.message ??
        `Lookup failed for ${pendingLookup.queryLabel}. Try adding the company website to disambiguate (example: "Aethria aethria.com").`,
    );
    setPendingLookup(null);
  }, [pendingLookup, pendingLookupMatch, lookupFailureQuery.data]);

  // Keep the startups list fresh while a lookup is in-flight so the new row
  // appears promptly instead of waiting for the normal list refresh interval.
  useEffect(() => {
    if (!pendingLookup || pendingLookupMatch) return;
    if (!liveGate.tabVisible || !liveGate.userActive) return;

    void queryClient.invalidateQueries({ queryKey: ['startups', 'list'] });
    const intervalId = window.setInterval(() => {
      void queryClient.invalidateQueries({ queryKey: ['startups', 'list'] });
    }, 3_000);

    return () => window.clearInterval(intervalId);
  }, [pendingLookup, pendingLookupMatch, liveGate.tabVisible, liveGate.userActive, queryClient]);

  useEffect(() => {
    if (!pendingLookup) return;
    const matched = pendingLookupMatch;
    if (!matched) {
      setMessage(
        `Searching sources for ${pendingLookup.queryLabel} and confirming the exact company identity...`,
      );
      return;
    }
    // Company Resolver transparency: weak identity evidence is announced, not hidden.
    const resolutionStatus = (matched.scout.resolution_status ?? '').toString().toUpperCase();
    const resolutionNote =
      resolutionStatus === 'PARTIAL'
        ? ' Evidence is partial — the memo lists what was found and what is missing.'
        : resolutionStatus === 'LOW_CONFIDENCE'
          ? ' Identity evidence is thin — kept and flagged for your review.'
          : resolutionStatus === 'NEEDS_REVIEW'
            ? ' Identity needs your confirmation — see alternatives in the memo.'
            : '';
    const hasDecision = !!matched.partner?.recommendation;
    if (hasDecision) {
      setMessage(
        `Lookup complete: ${matched.scout.name} analyzed.${resolutionNote} Review the result and open the memo.`,
      );
    } else if (matched.review) {
      setMessage(
        `Found ${matched.scout.name}.${resolutionNote} Review is complete and the partner decision is now running...`,
      );
    } else {
      setMessage(`Found ${matched.scout.name}.${resolutionNote} Running analyst review and scoring...`);
    }
    // No silent auto-navigation: the takeover surfaces the result overview with an
    // "Open memo" action (openLookupMemo) so the user advances deliberately.
  }, [pendingLookup, pendingLookupMatch]);

  const lookupWorking = busy || (pendingLookup != null && !pendingLookup.autoOpened);

  const phaseLabel: LookupPhaseLabel = !lookupWorking
    ? null
    : !pendingLookupMatch
      ? 'Scouting'
      : pendingLookupMatch.review
        ? 'Deciding'
        : 'Reviewing';

  // The queue row is thin (no per-dimension scores). Fetch full detail once the
  // lookup has a decision so the result overview shows real MKT/EXEC/… numbers.
  const lookupDetailQuery = useQuery({
    queryKey: ['startup', 'detail', pendingLookupMatch?.id],
    queryFn: () => fetchStartupDetail(pendingLookupMatch!.id),
    enabled: Boolean(
      commandBarOpen && pendingLookupMatch?.id && pendingLookupMatch?.partner?.recommendation,
    ),
    ...getQueryConfig('STATIC'),
  });

  const snapshotProps = useMemo(() => {
    const src = lookupDetailQuery.data ?? pendingLookupMatch;
    if (!src) return null;
    return buildLookupSnapshotProps(src, pendingLookup?.queryLabel, fundConfiguration?.verdictBadges);
  }, [lookupDetailQuery.data, pendingLookupMatch, pendingLookup?.queryLabel, fundConfiguration?.verdictBadges]);

  // In-flight lookup → drives the takeover's progressive reveal (null once decided).
  const progress = useMemo((): LookupProgress | null => {
    if (!pendingLookup) return null;
    if (pendingLookupMatch?.partner?.recommendation) return null;
    return {
      query: pendingLookup.queryLabel,
      name: pendingLookupMatch?.scout?.name ?? null,
      sector: pendingLookupMatch?.scout?.sector ?? null,
      found: !!pendingLookupMatch,
      reviewed: !!pendingLookupMatch?.review,
    };
  }, [pendingLookup, pendingLookupMatch]);

  // A finished lookup the analyst hasn't opened yet → "ready" toast.
  const lookupReady =
    !commandBarOpen && pendingLookup != null && !pendingLookup.autoOpened
      ? pendingLookupMatch?.partner?.recommendation
        ? pendingLookupMatch
        : null
      : null;

  const openLookupMemo = useCallback(() => {
    if (!pendingLookupMatch) return;
    onOpenMemo(pendingLookupMatch);
    // Opened → clear the active lookup entirely (don't auto-jump to another).
    // Any backgrounded lookups remain as chips, reachable on reopen.
    setPendingLookup(null);
    setCommandBarOpen(false); // close the takeover so the memo is visible
  }, [pendingLookupMatch, onOpenMemo]);

  const dismissReady = useCallback(() => {
    setPendingLookup((prev) => (prev ? { ...prev, autoOpened: true } : prev));
  }, []);

  // Resolve a tracked lookup's startup row (status from the live list).
  const findLookupMatch = useCallback(
    (id: string) =>
      startups.find(
        (s) =>
          (s.scout.origin_type ?? '').toLowerCase() === 'on_demand_lookup' &&
          (s.scout.lookup_id ?? '').trim() === id.trim(),
      ) ?? null,
    [startups],
  );

  // Chips for the takeover: active lookup first, then backgrounded ones.
  const chips = useMemo((): LookupChip[] => {
    const all = [pendingLookup, ...backgroundLookups].filter(Boolean) as TrackedLookup[];
    return all.map((l) => {
      const m = findLookupMatch(l.lookupId);
      const status: 'scouting' | 'reviewing' | 'decided' = m?.partner?.recommendation
        ? 'decided'
        : m?.review
          ? 'reviewing'
          : 'scouting';
      return {
        id: l.lookupId,
        label: m?.scout?.name || l.queryLabel,
        status,
        active: l.lookupId === pendingLookup?.lookupId,
      };
    });
  }, [pendingLookup, backgroundLookups, findLookupMatch]);

  // Focus a backgrounded lookup: swap it into active, demote the current one.
  const focusChip = useCallback(
    (id: string) => {
      if (id === pendingLookup?.lookupId) return;
      const target = backgroundLookups.find((l) => l.lookupId === id);
      if (!target) return;
      const demoted = pendingLookup && !pendingLookup.autoOpened ? pendingLookup : null;
      setBackgroundLookups((bg) => {
        const without = bg.filter((l) => l.lookupId !== id);
        return demoted ? [demoted, ...without.filter((l) => l.lookupId !== demoted.lookupId)] : without;
      });
      setPendingLookup(target);
    },
    [pendingLookup, backgroundLookups],
  );

  const openCommandBar = useCallback(() => setCommandBarOpen(true), []);
  // Closing keeps the tracked lookup intact so reopening returns to its live
  // state (progress or result). It clears only when the analyst opens its memo
  // or dismisses the ready toast (both set autoOpened).
  const closeCommandBar = useCallback(() => setCommandBarOpen(false), []);

  return {
    commandBarOpen,
    openCommandBar,
    closeCommandBar,
    input,
    setInput,
    submit,
    cancel,
    busy,
    message,
    clearMessage: () => setMessage(null),
    phaseLabel,
    progress,
    chips,
    focusChip,
    snapshotProps,
    pendingLookupMatch,
    openLookupMemo,
    lookupReady,
    dismissReady,
    lookupWorking,
  };
}
