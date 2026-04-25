import { useMemo, useState, useRef, useCallback, useEffect } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { createPortal } from 'react-dom';
import { motion, AnimatePresence } from 'framer-motion';
import { useNavigate } from 'react-router';
import { tokens } from '../design-system/tokens';
import SystemBar from './SystemBar';
import MobileHeader from './MobileHeader';
import PanelShell from './PanelShell';
import WorkGrid from './WorkGrid';
import InvestmentMemo from './InvestmentMemo';
import LiveIntelligenceFeed from './LiveIntelligenceFeed';
import GhostTransition from './GhostTransition';
import SystemIntelligence from './SystemIntelligence';
import AgentDispatch from './AgentDispatch';
import {
  useScrollLock,
  useEscapeKey,
  useRestoreFocus,
  useFocusTrap,
  useMediaQuery,
  usePrefersReducedMotion,
} from '../hooks';
import { transitionOrReduced } from '../design-system/motion';
import { UI_PANEL_CHROME_LABEL } from '../design-system/ui-text';
import type { Startup } from '../types/startup';
import type { SystemData } from '../hooks/useSystemData';
import InvestmentMemoContent, { type InvestmentMemoContentHandle } from './InvestmentMemoContent';
import { queueOnDemandLookup, fetchStartupDetail, fetchLookupJobStatus } from '../api/startups';
import {
  fetchAgentsStatus,
} from '../api/agents';
import { fetchFundThesisSummary } from '../api/fundThesis';
import { getQueryConfig } from '../lib/queryIntent';

const SYSTEM_MEMO_HEADER_PADDING = 'py-[10px]';
const MAIN_LAYOUT_STATE_KEY = 'aethria.mainLayout.v1';
const SETTINGS_PATH = '/v1/settings';

const PANEL_CHROME_ACTION_BTN_CLASS =
  `${UI_PANEL_CHROME_LABEL} rounded-none border-0 bg-transparent p-0 cursor-pointer hover:text-oxford/80 transition-colors duration-150 ease-out btn-interaction focus:outline-none focus-visible:ring-2 focus-visible:ring-oxford/40 focus-visible:ring-inset`;

interface MainLayoutProps {
  data: SystemData;
  startupsError?: string | null;
  onSystemPanelOpenChange?: (open: boolean) => void;
}

type PersistedMainLayoutState = {
  rightPanel: 'memo' | 'feed' | 'system' | null;
  selectedStartupId: string | null;
};

function readPersistedMainLayoutState(): PersistedMainLayoutState | null {
  if (typeof window === 'undefined') return null;
  try {
    const raw = window.localStorage.getItem(MAIN_LAYOUT_STATE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as Partial<PersistedMainLayoutState>;
    const panel = parsed.rightPanel;
    const rightPanel =
      panel === 'memo' || panel === 'feed' || panel === 'system'
        ? panel
        : null;
    return {
      rightPanel,
      selectedStartupId:
        typeof parsed.selectedStartupId === 'string' && parsed.selectedStartupId.trim()
          ? parsed.selectedStartupId.trim()
          : null,
    };
  } catch {
    return null;
  }
}

export default function MainLayout({
  data,
  startupsError,
  onSystemPanelOpenChange,
}: MainLayoutProps) {
  const {
    startups,
    signals,
    metaReports,
    rejectionAnalytics,
    watchlistAnalytics,
    concentrationAnalytics,
    scoutWeights,
    calibrationState,
    liveGate,
  } = data;
  const persistedStateRef = useRef<PersistedMainLayoutState | null>(readPersistedMainLayoutState());
  const hydratedFromStorageRef = useRef(false);
  const [selectedStartup, setSelectedStartup] = useState<Startup | null>(null);
  const [rightPanel, setRightPanel] = useState<'memo' | 'feed' | 'system' | null>(
    persistedStateRef.current?.rightPanel ?? null
  );
  const initialFirstMemoOpened = useRef(false);
  const [lookupInput, setLookupInput] = useState('');
  const [lookupBusy, setLookupBusy] = useState(false);
  const [lookupMessage, setLookupMessage] = useState<string | null>(null);
  const [showPipelineIssueHelp, setShowPipelineIssueHelp] = useState(false);
  const [pendingLookup, setPendingLookup] = useState<{
    lookupId: string;
    queryLabel: string;
    autoOpened: boolean;
  } | null>(null);

  const isDesktop = useMediaQuery('(min-width: 1024px)');
  const reduceMotion = usePrefersReducedMotion();
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const restoreRefVerdictMemo = useRef<HTMLElement | null>(null);
  const judgementsPanelRef = useRef<HTMLDivElement | null>(null);
  const memoContentRef = useRef<InvestmentMemoContentHandle | null>(null);
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const handleMemoPipelineReady = useCallback(() => {
    const id = selectedStartup?.id;
    if (id) void queryClient.invalidateQueries({ queryKey: ['startup', 'detail', id] });
  }, [queryClient, selectedStartup?.id]);

  const memoOpen = !!selectedStartup;
  const startupDetailQuery = useQuery({
    queryKey: ['startup', 'detail', selectedStartup?.id],
    queryFn: () => fetchStartupDetail(selectedStartup!.id),
    enabled: Boolean(selectedStartup?.id && memoOpen),
    ...getQueryConfig('STATIC'),
  });
  /** Full payload for memo (list row is thin; detail fetched on demand). */
  const memoStartup = startupDetailQuery.data ?? selectedStartup;
  const verdictOrMemoOpen = memoOpen;
  const judgementsAsOverlay = rightPanel === 'feed' && !isDesktop;
  /** System replaces the work grid (left column); never an overlay. */
  const anyOverlayOpen = verdictOrMemoOpen || judgementsAsOverlay;
  const useModal = selectedStartup && !isDesktop;

  const handleStartupClick = useCallback((startup: Startup) => {
    restoreRefVerdictMemo.current = document.activeElement as HTMLElement | null;
    setRightPanel('memo');
    setSelectedStartup(startup);
  }, []);

  const handleCloseMemo = useCallback(() => {
    setSelectedStartup(null);
    setRightPanel(null);
  }, []);

  const handleCloseJudgements = useCallback(() => {
    setRightPanel((panel) => (panel === 'feed' ? null : panel));
  }, []);

  const handleLookupSubmit = useCallback(async () => {
    const value = lookupInput.trim();
    if (!value || lookupBusy) return;
    setLookupBusy(true);
    setLookupMessage('Submitting lookup request...');
    try {
      const lookupId = crypto.randomUUID();
      const queued = await queueOnDemandLookup(value, lookupId);
      setPendingLookup({
        lookupId: queued.lookupId,
        queryLabel: value,
        autoOpened: false,
      });
      setLookupMessage(
        `Lookup queued for ${queued.companyName}. We are now finding and validating the company profile.`
      );
      setLookupInput('');
    } catch {
      setLookupMessage('Could not submit lookup request. Please retry in a few seconds.');
    } finally {
      setLookupBusy(false);
    }
  }, [lookupInput, lookupBusy]);

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
      pendingLookup && !pendingLookupMatch && pendingLookup.lookupId.trim().length > 0
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
    setLookupMessage(
      row.message ??
      `Lookup failed for ${pendingLookup.queryLabel}. Try adding the company website to disambiguate (example: "Aethria aethria.com").`
    );
    setPendingLookup(null);
  }, [pendingLookup, pendingLookupMatch, lookupFailureQuery.data]);

  // Keep WorkGrid fresh while on-demand lookup is in-flight so the new startup
  // appears promptly instead of waiting for the normal list refresh interval.
  useEffect(() => {
    if (!pendingLookup || pendingLookupMatch) return;
    if (!liveGate.tabVisible || !liveGate.userActive) return;

    void queryClient.invalidateQueries({ queryKey: ['startups', 'list'] });
    const intervalId = window.setInterval(() => {
      void queryClient.invalidateQueries({ queryKey: ['startups', 'list'] });
    }, 3_000);

    return () => window.clearInterval(intervalId);
  }, [
    pendingLookup,
    pendingLookupMatch,
    liveGate.tabVisible,
    liveGate.userActive,
    queryClient,
  ]);

  useEffect(() => {
    if (hydratedFromStorageRef.current) return;
    const persisted = persistedStateRef.current;
    if (!persisted?.selectedStartupId || startups.length === 0) {
      hydratedFromStorageRef.current = true;
      return;
    }
    const startup = startups.find((s) => s.id === persisted.selectedStartupId) ?? null;
    if (startup) {
      setSelectedStartup(startup);
      if (!persisted.rightPanel) setRightPanel('memo');
      initialFirstMemoOpened.current = true;
    }
    hydratedFromStorageRef.current = true;
  }, [startups]);

  useEffect(() => {
    if (initialFirstMemoOpened.current || startups.length === 0) return;
    initialFirstMemoOpened.current = true;
    setSelectedStartup(startups[0]);
    setRightPanel('memo');
  }, [startups]);

  useEffect(() => {
    if (!pendingLookup) return;
    const matched = pendingLookupMatch;
    if (!matched) {
      setLookupMessage(
        `Searching sources for ${pendingLookup.queryLabel} and confirming the exact company identity...`
      );
      return;
    }
    const hasDecision = !!matched.partner?.recommendation;
    if (hasDecision) {
      setLookupMessage(
        `Lookup complete: ${matched.scout.name} was analyzed successfully. Opening memo now...`
      );
    } else if (matched.review) {
      setLookupMessage(
        `Found ${matched.scout.name}. Review is complete and the partner decision is now running...`
      );
    } else {
      setLookupMessage(`Found ${matched.scout.name}. Running analyst review and scoring...`);
    }
    if (hasDecision && !pendingLookup.autoOpened) {
      setSelectedStartup(matched);
      setRightPanel('memo');
      setPendingLookup((prev) => (prev ? { ...prev, autoOpened: true } : prev));
    }
  }, [pendingLookup, pendingLookupMatch]);

  const handleEscape = useCallback(() => {
    if (memoOpen) handleCloseMemo();
    else if (rightPanel === 'feed') handleCloseJudgements();
    else if (rightPanel === 'system') setRightPanel(null);
  }, [memoOpen, rightPanel, handleCloseMemo, handleCloseJudgements]);

  useScrollLock(anyOverlayOpen);
  useEscapeKey(handleEscape, anyOverlayOpen);
  useRestoreFocus(verdictOrMemoOpen, restoreRefVerdictMemo, !judgementsAsOverlay);
  useRestoreFocus(judgementsAsOverlay, { current: null }, !verdictOrMemoOpen);
  useFocusTrap(judgementsAsOverlay, judgementsPanelRef);

  const resolvedCount = startups.filter((s) => s.partner?.recommendation != null).length;
  const openCount = Math.max(0, startups.length - resolvedCount);
  const pendingEscalations = data.settings?.system_health?.pending_escalations ?? 0;
  const agentConfig = data.settings?.agent_config;
  const pipelineEnabled =
    !!agentConfig && !!(agentConfig.scouts_enabled || agentConfig.reviewers_enabled || agentConfig.partners_enabled);
  const lookupWorking = lookupBusy || (pendingLookup != null && !pendingLookup.autoOpened);

  const { data: agentsStatus } = useQuery({
    queryKey: ['agents-status'],
    queryFn: () => fetchAgentsStatus().catch(() => null),
    ...getQueryConfig('SEMI_DYNAMIC', { liveGate }),
  });


  const fundThesisQuery = useQuery({
    queryKey: ['fund-thesis', 'summary'],
    queryFn: () => fetchFundThesisSummary().catch(() => null),
    ...getQueryConfig('SEMI_DYNAMIC', { liveGate, pollIntervalMs: 30_000 }),
    placeholderData: (prev) => prev ?? null,
  });
  const fundThesisSummary = fundThesisQuery.data ?? null;

  const lookupPhaseLabel = !lookupWorking
    ? null
    : !pendingLookupMatch
      ? 'Scouting'
      : pendingLookupMatch.review
        ? 'Deciding'
        : 'Reviewing';
  const pipelineHealthIssue =
    pipelineEnabled &&
    agentsStatus != null &&
    (!agentsStatus.worker_ready || !agentsStatus.supabase_configured || !agentsStatus.openai_configured);
  const pipelineStateLabel = !pipelineEnabled
    ? 'Off'
    : pipelineHealthIssue
      ? 'Issue'
      : 'On';
  useEffect(() => {
    onSystemPanelOpenChange?.(rightPanel === 'system');
  }, [rightPanel, onSystemPanelOpenChange]);

  useEffect(() => {
    if (typeof window === 'undefined') return;
    const snapshot: PersistedMainLayoutState = {
      rightPanel,
      selectedStartupId: selectedStartup?.id ?? null,
    };
    try {
      window.localStorage.setItem(MAIN_LAYOUT_STATE_KEY, JSON.stringify(snapshot));
    } catch {
      // ignore storage write failures (private mode/quota)
    }
  }, [rightPanel, selectedStartup?.id]);

  useEffect(() => {
    if (!pipelineHealthIssue && showPipelineIssueHelp) {
      setShowPipelineIssueHelp(false);
    }
  }, [pipelineHealthIssue, showPipelineIssueHelp]);

  const watchlistIds = useMemo(() => {
    const ids = new Set<string>();
    for (const e of watchlistAnalytics?.entries ?? []) {
      if (e?.startup_id) ids.add(e.startup_id);
    }
    return ids;
  }, [watchlistAnalytics]);

  const hasThesis = !!fundThesisSummary?.active_version_id;
  const fundName = useMemo(() => {
    // Prefer parsed_json name fields from the thesis itself
    const pj = fundThesisSummary?.parsed_json;
    if (pj && typeof pj === 'object') {
      for (const key of ['fund_name', 'name', 'title', 'fund', 'fund_title']) {
        const val = (pj as Record<string, unknown>)[key];
        if (typeof val === 'string' && val.trim()) return val.trim();
      }
    }
    // Fall back to settings fund identity
    const settingsName = data.settings?.fund_identity?.fund_name?.trim();
    if (settingsName) return settingsName;
    // Last resort: version label if thesis exists
    if (fundThesisSummary?.active_version_number != null) {
      return `Fund Thesis v${fundThesisSummary.active_version_number}`;
    }
    return '';
  }, [fundThesisSummary, data.settings?.fund_identity?.fund_name]);

  const fundStage = data.settings?.fund_identity?.stage_focus?.trim() || '';
  const fundGeo = data.settings?.fund_identity?.geographic_focus?.trim() || '';
  const scoutRegionRaw = data.settings?.agent_config?.scout_region?.trim() || '';
  const scoutRegion =
    scoutRegionRaw.length > 0
      ? scoutRegionRaw.charAt(0).toUpperCase() + scoutRegionRaw.slice(1).toLowerCase()
      : '';
  const thesisTags = useMemo(() => {
    const pj = fundThesisSummary?.parsed_json as Record<string, unknown> | undefined;
    const toStrings = (v: unknown): string[] => {
      if (Array.isArray(v)) return v.filter((x): x is string => typeof x === 'string' && !!x.trim()).map((x) => x.trim());
      if (typeof v === 'string' && v.trim()) return [v.trim()];
      return [];
    };
    const sectors = pj ? toStrings(pj.sectors ?? pj.sector ?? pj.focus_areas) : toStrings(undefined);
    const stages = pj ? toStrings(pj.stage_focus ?? pj.stage) : toStrings(fundStage);
    const geos = pj ? toStrings(pj.geography ?? pj.geographies ?? pj.geographic_focus) : toStrings(undefined);
    // Fall back to settings if parsed_json has nothing
    return {
      sectors,
      stages: stages.length ? stages : fundStage ? [fundStage] : [],
      geos: geos.length ? geos : fundGeo ? [fundGeo] : scoutRegion ? [scoutRegion] : [],
    };
  }, [fundThesisSummary, fundStage, fundGeo, scoutRegion]);

  return (
    <div className="h-[100dvh] flex flex-col overflow-hidden bg-paper">
      {/* Mobile / tablet top nav — desktop keeps the vertical SystemBar only */}
      {!isDesktop && (
        <>
          <MobileHeader onMenuToggle={() => setMobileMenuOpen((open) => !open)} />
          <AnimatePresence>
            {mobileMenuOpen && (
              <motion.section
                id="mobile-menu"
                initial={{ opacity: 0, y: -8 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -8 }}
                transition={transitionOrReduced(reduceMotion, {
                  duration: tokens.motion.duration.micro,
                  ease: tokens.motion.ease,
                })}
                className="border-b border-hairline type-label-tab bg-oxford text-white/70"
                aria-label="Menu"
              >
                <div className="px-4 pb-0">
                <div className="flex flex-col items-start gap-phi-3 py-phi-3">
                  {/* Mode toggles: Deals / Judgements / System — same mono scale as desktop spine */}
                  <div className="flex flex-col items-stretch gap-phi-1 w-full">
                    <button
                      type="button"
                      onClick={() => {
                        setRightPanel((panel) => (panel === 'feed' ? null : 'feed'));
                        setMobileMenuOpen(false);
                      }}
                      className={`type-meta min-h-[44px] flex items-center justify-start cursor-pointer px-0 uppercase tracking-[0.12em] btn-interaction ${rightPanel === 'feed' ? 'text-white' : 'text-white/55 hover:text-white'
                        }`}
                      style={{ transitionTimingFunction: 'var(--motion-ease)' }}
                      aria-pressed={rightPanel === 'feed'}
                    >
                      <span
                        className={`inline-block pb-0.5 ${rightPanel === 'feed' ? 'border-b border-white' : ''}`}
                      >
                        Judgements
                      </span>
                    </button>
                    <button
                      type="button"
                      onClick={() => {
                        setRightPanel((p) => (p === 'system' ? null : p));
                        setMobileMenuOpen(false);
                      }}
                      className={`type-meta min-h-[44px] flex items-center justify-start cursor-pointer px-0 uppercase tracking-[0.12em] btn-interaction ${rightPanel !== 'system' && rightPanel !== 'feed'
                        ? 'text-white'
                        : 'text-white/55 hover:text-white'
                        }`}
                      style={{ transitionTimingFunction: 'var(--motion-ease)' }}
                      aria-pressed={rightPanel !== 'system' && rightPanel !== 'feed'}
                    >
                      <span
                        className={`inline-block pb-0.5 ${rightPanel !== 'system' && rightPanel !== 'feed' ? 'border-b border-white' : ''}`}
                      >
                        Deals
                      </span>
                    </button>
                    <button
                      type="button"
                      onClick={() => {
                        setRightPanel((panel) => (panel === 'system' ? null : 'system'));
                        setMobileMenuOpen(false);
                      }}
                      className={`type-meta min-h-[44px] flex items-center justify-start cursor-pointer px-0 uppercase tracking-[0.12em] btn-interaction ${rightPanel === 'system' ? 'text-white' : 'text-white/55 hover:text-white'
                        }`}
                      style={{ transitionTimingFunction: 'var(--motion-ease)' }}
                      aria-pressed={rightPanel === 'system'}
                    >
                      <span
                        className={`inline-block pb-0.5 ${rightPanel === 'system' ? 'border-b border-white' : ''}`}
                      >
                        System
                      </span>
                    </button>
                  </div>

                  {/* Settings */}
                  <div className="flex flex-col items-start gap-phi-1 mt-phi-3">
                    <button
                      type="button"
                      onClick={() => navigate(SETTINGS_PATH)}
                      className="type-label-section text-white/70 hover:text-white btn-interaction"
                    >
                      Settings
                    </button>
                  </div>
                </div>
                </div>
              </motion.section>
            )}
          </AnimatePresence>
        </>
      )}

      <SystemBar
        rightPanel={rightPanel}
        onShowDeals={() => setRightPanel((p) => (p === 'system' ? null : p))}
        onShowFeed={() => setRightPanel((panel) => (panel === 'feed' ? null : 'feed'))}
        onShowSystem={() => setRightPanel((panel) => (panel === 'system' ? null : 'system'))}
        onClose={() => setRightPanel(null)}
        navLink={{ href: SETTINGS_PATH, label: 'Settings' }}
      />
      {startupsError && (
        <div className="flex-none px-6 py-2 bg-warning border-b border-oxford/25 type-label-tab text-oxford">
          {startupsError} — Check API URL (VITE_API_URL) and backend CORS (ALLOWED_ORIGINS).
        </div>
      )}

      {/* Paper canvas. Fixed height so only WorkGrid scrolls.
          On desktop content is offset to clear vertical SystemBar; on mobile it uses standard page padding. */}
      <main className="flex-1 flex flex-col min-h-0 overflow-hidden px-phi-4 pt-phi-3 lg:pl-[calc(9rem+var(--space-4))] lg:pr-phi-4 lg:pt-phi-4">
        <div className="flex-1 flex flex-col min-h-0 overflow-hidden">
          <div className="flex-1 flex flex-col lg:grid lg:grid-cols-[6fr_7fr] min-h-0 overflow-hidden pb-phi-3 lg:pb-phi-4 gap-phi-4 lg:gap-phi-5">
            <div className="flex min-w-0 min-h-0 flex-1 flex-col lg:min-h-0">
              {/* Pipeline summary + lookup */}
              <header className="flex-none mb-phi-4 min-w-0 lg:px-0">
                <section
                  aria-label="Pipeline summary and agent status"
                  className="flex min-w-0 flex-wrap items-center justify-between gap-x-phi-4 gap-y-phi-1 pb-phi-3 px-phi-4"
                >
                  <p className="min-w-0 type-meta tracking-label uppercase text-oxford/40">
                    <span className="text-oxford/60">{startups.length}</span> total
                    <span className="mx-phi-2 text-oxford/25">·</span>
                    <span className="text-oxford/60">{openCount}</span> open
                    <span className="mx-phi-2 text-oxford/25">·</span>
                    <span className={pendingEscalations > 0 ? 'text-escalation' : 'text-oxford/60'}>{pendingEscalations}</span> esc
                    <span className="mx-phi-2 text-oxford/25">·</span>
                    <span className="text-oxford/60">{resolvedCount}</span> decided
                    {signals.length > 0 && (
                      <>
                        <span className="mx-phi-2 text-oxford/25">·</span>
                        <span className="text-oxford/60">{signals.length}</span> sig
                      </>
                    )}
                  </p>
                  <p className="shrink-0 text-right type-meta tracking-label uppercase text-oxford/40">
                    Pipeline{' '}
                    <span className="relative inline-flex items-center gap-phi-2">
                      {/* Live dot — shown when pipeline is On (implies enabled and no issue) */}
                      {pipelineStateLabel === 'On' && (
                        <span
                          className="h-1.5 w-1.5 shrink-0 rounded-none bg-oxford/60"
                          style={{
                            animation: pipelineStateLabel === 'On'
                              ? 'aethria-pulse 2.4s cubic-bezier(0.16,1,0.3,1) infinite'
                              : 'aethria-pulse 1.2s cubic-bezier(0.16,1,0.3,1) infinite'
                          }}
                          aria-hidden
                        />
                      )}
                      <span className={
                        pipelineStateLabel === 'Issue' ? 'text-escalation' :
                          pipelineStateLabel === 'Off' ? 'text-oxford/45' :
                            pipelineStateLabel === 'On' ? 'text-oxford/80' :
                      /* Working */                      'text-oxford/60'
                      }>
                        {pipelineStateLabel}
                      </span>
                      {pipelineStateLabel === 'Issue' && (
                        <>
                          <button
                            type="button"
                            onClick={() => setShowPipelineIssueHelp((open) => !open)}
                            className="inline-flex h-3.5 w-3.5 items-center justify-center rounded-none border border-escalation/40 type-meta leading-none text-escalation hover:bg-escalation/10 btn-interaction focus:outline-none focus-visible:ring-2 focus-visible:ring-escalation/40"
                            aria-label="Why pipeline has an issue"
                            aria-expanded={showPipelineIssueHelp}
                          >
                            ?
                          </button>
                          {showPipelineIssueHelp && (
                            <span className="absolute right-0 top-[calc(100%+6px)] z-20 w-56 border border-field-border bg-paper p-phi-3 text-left normal-case tracking-normal type-label-section leading-phi text-oxford">
                              Pipeline has a problem and may not process updates right now.
                              <button
                                type="button"
                                onClick={() => navigate(SETTINGS_PATH)}
                                className="mt-phi-2 block type-meta tracking-badge uppercase text-oxford/60 hover:text-oxford btn-interaction"
                              >
                                Open settings →
                              </button>
                            </span>
                          )}
                        </>
                      )}
                    </span>
                  </p>
                </section>
                <AgentDispatch
                  input={lookupInput}
                  setInput={setLookupInput}
                  onSubmit={() => void handleLookupSubmit()}
                  isBusy={lookupBusy}
                  message={lookupMessage}
                  lookupPhase={lookupPhaseLabel}
                />
              </header>

              {/* Fund thesis — mobile only (desktop shows it in the right column) */}
              <div className="flex-none mb-phi-2 block lg:hidden">
                <article
                  className="w-full border border-hairline bg-paper px-phi-3 py-phi-2"
                  style={{ boxSizing: 'border-box' }}
                  aria-label="Fund thesis preview"
                >
                  <div className="flex items-center justify-between gap-phi-2">
                    <p className="type-meta tracking-label uppercase text-oxford/40">
                      Active Mandate · Fund Thesis
                    </p>
                    {hasThesis && (
                      <span className="inline-flex items-center gap-phi-1">
                        <span
                          className="h-1.5 w-1.5 shrink-0 rounded-none bg-oxford signal-dot-breathe"
                          style={{ opacity: 0.6 }}
                          aria-hidden
                        />
                        <span className="type-meta tracking-badge uppercase text-oxford/40">Live</span>
                      </span>
                    )}
                  </div>
                  <p className="mt-phi-1 type-body-sm font-semibold tracking-tight text-oxford">
                    {fundName || 'No fund configured'}
                  </p>
                  {(thesisTags.sectors.length > 0 || thesisTags.stages.length > 0 || thesisTags.geos.length > 0) && (
                    <div className="mt-phi-2 flex flex-wrap gap-phi-1">
                      {[...thesisTags.sectors, ...thesisTags.stages, ...thesisTags.geos].map((t) => (
                        <span key={t} className="border border-hairline px-phi-2 py-phi-1 type-meta text-oxford/40">{t}</span>
                      ))}
                    </div>
                  )}
                </article>
              </div>

              <div
                className="flex-1 min-h-0 overflow-y-auto overscroll-contain w-full min-w-0 rounded-none bg-paper"
                style={{ scrollbarGutter: 'stable both-edges' }}
              >
                {rightPanel === 'system' ? (
                  <SystemIntelligence
                    startups={startups}
                    signals={signals}
                    rejectionAnalytics={rejectionAnalytics}
                    watchlistAnalytics={watchlistAnalytics}
                    concentrationAnalytics={concentrationAnalytics}
                    metaReports={metaReports}
                    scoutWeights={scoutWeights}
                    calibrationState={calibrationState}
                    onClose={() => setRightPanel(null)}
                  />
                ) : (
                  <GhostTransition disableLift>
                    <WorkGrid
                      startups={startups}
                      onStartupClick={handleStartupClick}
                      selectedId={selectedStartup?.id ?? null}
                      watchlistIds={watchlistIds}
                    />
                  </GhostTransition>
                )}
              </div>
            </div>

            {/* Right zone: Judgements or memo only — never System. */}
            <div className="hidden lg:flex min-w-0 min-h-0 flex-col gap-phi-3">
              <article
                className="w-full border border-hairline bg-paper p-phi-5"
                style={{ boxSizing: 'border-box' }}
                aria-label="Fund thesis preview"
              >
                <div className="flex items-center justify-between gap-phi-2">
                  <p className="type-label-section text-oxford/40">
                    Active Mandate · Fund Thesis
                  </p>
                  {hasThesis && (
                    <span className="inline-flex items-center gap-phi-2">
                      <span
                        className="h-1.5 w-1.5 shrink-0 rounded-none bg-oxford signal-dot-breathe"
                        style={{ opacity: 0.6 }}
                        aria-hidden
                      />
                      <span className="type-meta tracking-badge uppercase text-oxford/40">Live</span>
                    </span>
                  )}
                </div>
                <p className="mt-phi-3 type-body font-semibold tracking-tight text-oxford">
                  {fundName || 'No fund configured'}
                </p>
                {(thesisTags.sectors.length > 0 || thesisTags.stages.length > 0 || thesisTags.geos.length > 0) && (
                  <div className="mt-phi-3 flex flex-wrap gap-phi-2">
                    {[...thesisTags.sectors, ...thesisTags.stages, ...thesisTags.geos].map((t) => (
                      <span key={t} className="border border-hairline px-phi-2 py-phi-1 type-meta text-oxford/40">{t}</span>
                    ))}
                  </div>
                )}
              </article>
              <aside
                className="min-w-0 min-h-0 flex-1 border border-hairline bg-paper overflow-hidden"
                aria-live="polite"
                aria-label={
                  rightPanel === 'feed'
                    ? 'Judgements'
                    : selectedStartup
                      ? 'Investment memo'
                      : 'Detail'
                }
              >
                <AnimatePresence mode="wait" initial={false}>
                  {rightPanel === 'feed' ? (
                    <motion.div
                      key="desktop-feed-panel"
                      initial={reduceMotion ? { opacity: 1, y: 0 } : { opacity: 0, y: 8 }}
                      animate={{ opacity: 1, y: 0 }}
                      exit={reduceMotion ? { opacity: 1, y: 0 } : { opacity: 0, y: -6 }}
                      transition={transitionOrReduced(reduceMotion, {
                        duration: tokens.motion.duration.short,
                        ease: tokens.motion.ease,
                      })}
                      className="h-full"
                    >
                      <PanelShell
                        className="min-h-0 flex-1"
                        title="JUDGEMENTS"
                        titleClassName={UI_PANEL_CHROME_LABEL}
                        headerPaddingClass={SYSTEM_MEMO_HEADER_PADDING}
                        headerBorderClass=""
                        actions={
                          <button
                            type="button"
                            onClick={handleCloseJudgements}
                            className={PANEL_CHROME_ACTION_BTN_CLASS}
                            aria-label="Hide judgements"
                          >
                            CLOSE
                          </button>
                        }
                        contentOverflowHidden
                        contentClassName="flex-1 min-h-0 overflow-hidden"
                      >
                        <LiveIntelligenceFeed
                          startups={startups}
                          signals={signals}
                          metaReports={metaReports}
                        />
                      </PanelShell>
                    </motion.div>
                  ) : selectedStartup ? (
                    <motion.div
                      key="desktop-memo-shell"
                      initial={reduceMotion ? { opacity: 1, y: 0 } : { opacity: 0, y: 8 }}
                      animate={{ opacity: 1, y: 0 }}
                      exit={reduceMotion ? { opacity: 1, y: 0 } : { opacity: 0, y: -6 }}
                      transition={transitionOrReduced(reduceMotion, {
                        duration: tokens.motion.duration.short,
                        ease: tokens.motion.ease,
                      })}
                      className="h-full"
                    >
                      <PanelShell
                        className="min-h-0 min-w-0 flex-1 w-full"
                        title=""
                        showTitle={false}
                        headerPaddingClass={SYSTEM_MEMO_HEADER_PADDING}
                        headerBorderClass=""
                        headerJustifyClass="justify-end"
                        actions={
                          <div className="flex items-center gap-phi-2">
                            <button
                              type="button"
                              onClick={() => memoContentRef.current?.downloadPDF()}
                              className={PANEL_CHROME_ACTION_BTN_CLASS}
                            >
                              IC PACK (PDF)
                            </button>
                            <button
                              type="button"
                              onClick={() => memoContentRef.current?.downloadMarkdown()}
                              className={PANEL_CHROME_ACTION_BTN_CLASS}
                            >
                              IC PACK (MD)
                            </button>
                            <button
                              type="button"
                              onClick={handleCloseMemo}
                              className={PANEL_CHROME_ACTION_BTN_CLASS}
                              aria-label="Close memo"
                            >
                              CLOSE
                            </button>
                          </div>
                        }
                        contentClassName="flex-1 min-h-0 overflow-y-auto px-6 py-6 sm:px-8 sm:py-8"
                      >
                        <AnimatePresence mode="wait" initial={false}>
                          <motion.div
                            key={memoStartup!.id}
                            initial={reduceMotion ? { opacity: 1, y: 0 } : { opacity: 0, y: 8 }}
                            animate={{ opacity: 1, y: 0 }}
                            exit={reduceMotion ? { opacity: 1, y: 0 } : { opacity: 0, y: -6 }}
                            transition={transitionOrReduced(reduceMotion, {
                              duration: tokens.motion.duration.short,
                              ease: tokens.motion.ease,
                            })}
                            className="h-full"
                          >
                            <InvestmentMemoContent
                              ref={memoContentRef}
                              startup={memoStartup!}
                              embedded
                              onMemoPipelineReady={handleMemoPipelineReady}
                            />
                          </motion.div>
                        </AnimatePresence>
                      </PanelShell>
                    </motion.div>
                  ) : (
                    <motion.div
                      key="desktop-empty-detail"
                      initial={reduceMotion ? { opacity: 1, y: 0 } : { opacity: 0, y: 8 }}
                      animate={{ opacity: 1, y: 0 }}
                      exit={reduceMotion ? { opacity: 1, y: 0 } : { opacity: 0, y: -6 }}
                      transition={transitionOrReduced(reduceMotion, {
                        duration: tokens.motion.duration.short,
                        ease: tokens.motion.ease,
                      })}
                      className="h-full"
                    >
                      <div className="flex-1 flex items-center justify-center p-8 h-full">
                        <p className="type-label-tab text-oxford/45" style={{ transition: 'opacity var(--motion-micro) var(--motion-ease)' }}>
                          Click a deal to open the memo here
                        </p>
                      </div>
                    </motion.div>
                  )}
                </AnimatePresence>
              </aside>
            </div>
          </div>
        </div>
      </main>

      {/* Judgements slide-over on mobile only; System swaps into the left column above. */}
      {judgementsAsOverlay && typeof document !== 'undefined' && createPortal(
        <AnimatePresence>
          <motion.div
            key="judgements-overlay"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={transitionOrReduced(reduceMotion, {
              duration: tokens.motion.duration.medium,
              ease: tokens.motion.ease,
            })}
            className="fixed inset-0 z-[9999]"
            style={{
              minHeight: '100dvh',
              width: '100vw',
              left: 0,
              top: 0,
              right: 0,
              bottom: 0,
              backgroundColor: 'var(--color-paper)',
              paddingTop: 'env(safe-area-inset-top)',
              paddingBottom: 'env(safe-area-inset-bottom)',
              paddingLeft: 'env(safe-area-inset-left)',
              paddingRight: 'env(safe-area-inset-right)',
            }}
            onClick={handleCloseJudgements}
            aria-hidden="true"
          />
          <motion.div
            ref={judgementsPanelRef}
            key="judgements-panel"
            initial={reduceMotion ? { x: 0 } : { x: '100%' }}
            animate={{ x: 0 }}
            exit={reduceMotion ? { x: 0 } : { x: '100%' }}
            transition={transitionOrReduced(reduceMotion, {
              duration: tokens.motion.duration.medium,
              ease: tokens.motion.ease,
            })}
            className="fixed top-0 right-0 w-full max-w-full sm:w-[380px] lg:w-[400px] z-[10000] flex flex-col bg-paper"
            style={{
              borderLeft: tokens.frameBorder,
              minHeight: '100dvh',
              height: '100dvh',
              paddingTop: 'env(safe-area-inset-top)',
              paddingBottom: 'env(safe-area-inset-bottom)',
              paddingRight: 'env(safe-area-inset-right)',
            }}
            onClick={(e) => e.stopPropagation()}
          >
            <PanelShell
              title="JUDGEMENTS"
              titleClassName={UI_PANEL_CHROME_LABEL}
              headerPaddingClass={SYSTEM_MEMO_HEADER_PADDING}
              headerBorderClass=""
              actions={
                <button
                  type="button"
                  onClick={handleCloseJudgements}
                  className={`${PANEL_CHROME_ACTION_BTN_CLASS} min-w-[44px] min-h-[44px] flex items-center justify-center`}
                  aria-label="Close judgements panel"
                >
                  CLOSE
                </button>
              }
              contentOverflowHidden
              contentClassName="flex-1 min-h-0 overflow-hidden"
              className="h-full"
            >
              <LiveIntelligenceFeed
                startups={startups}
                signals={signals}
                metaReports={metaReports}
              />
            </PanelShell>
          </motion.div>
        </AnimatePresence>,
        document.body
      )}

      {/* Memo modal on small viewports; on desktop the right panel shows the memo. */}
      <AnimatePresence initial={false}>
        {useModal && memoStartup && (
          <InvestmentMemo
            key={`memo-${memoStartup.id}`}
            startup={memoStartup}
            onClose={handleCloseMemo}
            onMemoPipelineReady={handleMemoPipelineReady}
          />
        )}
      </AnimatePresence>
    </div>
  );
}
