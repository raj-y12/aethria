import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useAuth } from '@clerk/react-router';
import {
  cancelOnDemandLookups,
  queueOnDemandLookup,
  fetchStartupDetail,
  fetchLookupJobStatus,
  resolveLookupCandidates,
  type LookupCandidate,
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

export interface LookupFailure {
  query: string;
  message: string;
}

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
  const [candidates, setCandidates] = useState<LookupCandidate[]>([]);
  const [refining, setRefining] = useState(false);
  // Active dispatch session: true from the moment the analyst submits until the
  // lookup resolves, fails, or is cleared. Drives the takeover straight to the
  // stages screen so identity confirmation + disambiguation live there, not on
  // the compose surface.
  const [dispatching, setDispatching] = useState(false);
  // Resolver returned no clear match — ask the analyst for a website to pin it.
  const [needsWebsite, setNeedsWebsite] = useState(false);
  // The analyst's own words for the lookup, kept for the stages-screen heading
  // before the scout has resolved a canonical company name.
  const [activeQuery, setActiveQuery] = useState('');
  const [pendingLookup, setPendingLookup] = useState<TrackedLookup | null>(null);
  // A lookup the scout could not resolve (company not found / ambiguous). Drives
  // the takeover's failure view — the "here's what we found" counterpart for misses.
  const [failure, setFailure] = useState<LookupFailure | null>(null);
  const [hydratedStorageKey, setHydratedStorageKey] = useState<string | null>(null);
  // Other in-flight lookups the analyst started via "Look up another". The active
  // one (pendingLookup) keeps the full polling machinery; these are chips that can
  // be focused (swapped into active) and read their status from the startups list.
  const [backgroundLookups, setBackgroundLookups] = useState<TrackedLookup[]>([]);
  const requestSeqRef = useRef(0);

  const storageKey = useMemo(() => getDispatchLookupStorageKey(userId), [userId]);

  const queueLookup = useCallback(
    async (value: string, requestSeq: number) => {
      const lookupId = crypto.randomUUID();
      const queued = await queueOnDemandLookup(value, lookupId);
      if (requestSeqRef.current !== requestSeq) return;
      const current = pendingLookup;
      if (current && !current.autoOpened && current.lookupId !== queued.lookupId) {
        setBackgroundLookups((bg) => [current, ...bg.filter((l) => l.lookupId !== current.lookupId)]);
      }
      setCandidates([]);
      setRefining(false);
      setNeedsWebsite(false);
      setPendingLookup({ lookupId: queued.lookupId, queryLabel: value, autoOpened: false });
      setMessage(
        `Lookup queued for ${queued.companyName}. We are now finding and validating the company profile.`,
      );
      setInput('');
    },
    [pendingLookup],
  );

  const submit = useCallback(async () => {
    const value = input.trim();
    if (!value || busy) return;
    const requestSeq = requestSeqRef.current + 1;
    requestSeqRef.current = requestSeq;
    setFailure(null);
    setDispatching(true);
    setActiveQuery(value);
    setNeedsWebsite(false);
    setCandidates([]);
    setBusy(true);
    setMessage('Confirming the company identity...');
    try {
      let resolved;
      try {
        resolved = await resolveLookupCandidates(value);
      } catch {
        // Fail-safe: resolve outage must not break dispatch — queue directly.
        await queueLookup(value, requestSeq);
        return;
      }
      if (requestSeqRef.current !== requestSeq) return;
      if (resolved.status === 'ambiguous') {
        setCandidates(resolved.candidates);
        setMessage('Multiple companies match — select the one you meant.');
        return;
      }
      if (resolved.status === 'not_found') {
        setCandidates([]);
        setNeedsWebsite(true);
        setMessage(
          `No clear match for ${value}. Add the company website to pin it (e.g. "${value} example.com").`,
        );
        return;
      }
      const pick = resolved.candidates[0];
      await queueLookup(pick ? `${pick.name} ${pick.website}` : value, requestSeq);
    } catch {
      setMessage('Could not submit lookup request. Please retry in a few seconds.');
    } finally {
      if (requestSeqRef.current === requestSeq) setBusy(false);
    }
  }, [input, busy, queueLookup]);

  const pickCandidate = useCallback(
    async (candidate: LookupCandidate) => {
      if (busy) return;
      const requestSeq = requestSeqRef.current + 1;
      requestSeqRef.current = requestSeq;
      setNeedsWebsite(false);
      setBusy(true);
      try {
        await queueLookup(`${candidate.name} ${candidate.website}`, requestSeq);
      } catch {
        setMessage('Could not submit lookup request. Please retry in a few seconds.');
      } finally {
        if (requestSeqRef.current === requestSeq) setBusy(false);
      }
    },
    [busy, queueLookup],
  );

  const refineWithWebsite = useCallback(
    async (websiteHint: string) => {
      const value = input.trim() || websiteHint.trim();
      const requestSeq = requestSeqRef.current + 1;
      requestSeqRef.current = requestSeq;
      setRefining(true);
      setBusy(true);
      try {
        const resolved = await resolveLookupCandidates(value, websiteHint);
        if (requestSeqRef.current !== requestSeq) return;
        if (resolved.status === 'ambiguous') {
          setCandidates(resolved.candidates);
          setNeedsWebsite(false);
          setMessage('Still more than one match — pick a candidate or refine again.');
          return;
        }
        if (resolved.status === 'not_found') {
          setCandidates([]);
          setNeedsWebsite(true);
          setMessage(
            `No company found at ${websiteHint}. Check the address and try again.`,
          );
          return;
        }
        const pick = resolved.candidates[0];
        await queueLookup(pick ? `${pick.name} ${pick.website}` : `${value} ${websiteHint}`, requestSeq);
      } catch {
        setMessage('Could not resolve that website. Please retry.');
      } finally {
        if (requestSeqRef.current === requestSeq) {
          setBusy(false);
          setRefining(false);
        }
      }
    },
    [input, queueLookup],
  );

  const cancel = useCallback(() => {
    const lookupIds = [
      pendingLookup?.lookupId,
      ...backgroundLookups.map((lookup) => lookup.lookupId),
    ].filter((id): id is string => Boolean(id?.trim()));
    requestSeqRef.current += 1;
    setBusy(false);
    setDispatching(false);
    setNeedsWebsite(false);
    setActiveQuery('');
    setPendingLookup(null);
    setBackgroundLookups([]);
    setFailure(null);
    setMessage(null);
    setInput('');
    setCandidates([]);
    setRefining(false);
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
      // A lookup in flight must keep checking even while the analyst sits still
      // watching the takeover — the idle gate would otherwise freeze failure
      // detection. Only stop when the tab is hidden or the job already failed.
      if (!liveGate.tabVisible) return false;
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
    const reason =
      row.message ??
      `We couldn't confirm a company matching "${pendingLookup.queryLabel}". Try the exact name or add the website to disambiguate (example: "Aethria aethria.com").`;
    setFailure({ query: pendingLookup.queryLabel, message: reason });
    setMessage(null);
    setDispatching(false);
    setNeedsWebsite(false);
    setPendingLookup(null);
    // Surface the fail page even if the analyst had closed the takeover.
    setCommandBarOpen(true);
  }, [pendingLookup, pendingLookupMatch, lookupFailureQuery.data]);

  // Keep the startups list fresh for the WHOLE in-flight lookup — not just until
  // the scout row first appears. Stopping at row-appearance left review→decide to
  // SSE + the idle-gated global poll alone; with the analyst idle on the takeover
  // (and SSE unreliable behind a buffering proxy) the row froze at Review, so it
  // never reached Decide and the result snapshot never rendered. Poll until a
  // partner recommendation lands (lookup decided), then stop.
  const lookupDecided = !!pendingLookupMatch?.partner?.recommendation;
  useEffect(() => {
    if (!pendingLookup || pendingLookup.autoOpened || lookupDecided) return;
    // Stay live through idle: the analyst watching the takeover isn't "active"
    // (mousemove doesn't reset the idle gate), so gating on userActive here would
    // stall the in-flight progress poll right when they're staring at it.
    if (!liveGate.tabVisible) return;

    void queryClient.invalidateQueries({ queryKey: ['startups', 'list'] });
    const intervalId = window.setInterval(() => {
      void queryClient.invalidateQueries({ queryKey: ['startups', 'list'] });
    }, 3_000);

    return () => window.clearInterval(intervalId);
  }, [pendingLookup, lookupDecided, liveGate.tabVisible, queryClient]);

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

  // Active dispatch → drives the takeover's stages screen. Non-null from the
  // moment of submit (identity confirmation / disambiguation) through the
  // in-flight pipeline, null once decided (the result snapshot takes over).
  const progress = useMemo((): LookupProgress | null => {
    if (!dispatching && !pendingLookup) return null;
    if (pendingLookupMatch?.partner?.recommendation) return null;
    return {
      query: activeQuery || pendingLookup?.queryLabel || '',
      name: pendingLookupMatch?.scout?.name ?? null,
      sector: pendingLookupMatch?.scout?.sector ?? null,
      // Identity confirmed once a lookup has actually been queued; until then the
      // analyst is still on the Identify stage (resolving / picking a candidate).
      resolved: pendingLookup != null,
      found: !!pendingLookupMatch,
      reviewed: !!pendingLookupMatch?.review,
    };
  }, [dispatching, activeQuery, pendingLookup, pendingLookupMatch]);

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
    setDispatching(false);
    setNeedsWebsite(false);
    setActiveQuery('');
    setPendingLookup(null);
    setCommandBarOpen(false); // close the takeover so the memo is visible
  }, [pendingLookupMatch, onOpenMemo]);

  const dismissReady = useCallback(() => {
    setPendingLookup((prev) => (prev ? { ...prev, autoOpened: true } : prev));
  }, []);

  // Leave the failure view (e.g. "Try again" → back to compose, or close).
  const dismissFailure = useCallback(() => setFailure(null), []);

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
      setFailure(null);
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
    failure,
    dismissFailure,
    lookupWorking,
    candidates,
    needsWebsite,
    pickCandidate,
    refineWithWebsite,
    refining,
  };
}
