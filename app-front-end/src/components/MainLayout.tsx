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
import AccountRailPanel from './AccountRailPanel';
import {
  useScrollLock,
  useEscapeKey,
  useRestoreFocus,
  useFocusTrap,
  useMediaQuery,
  usePrefersReducedMotion,
  useFundConfiguration,
} from '../hooks';
import { transitionOrReduced } from '../design-system/motion';
import {
  UI_PANEL_CHROME_LABEL,
} from '../design-system/ui-text';
import type { Startup } from '../types/startup';
import type { SystemData } from '../hooks/useSystemData';
import InvestmentMemoContent, { type InvestmentMemoContentHandle } from './InvestmentMemoContent';
import { queueOnDemandLookup, fetchStartupDetail, fetchLookupJobStatus } from '../api/startups';
import {
  fetchAgentsStatus,
  fetchLoopStatus,
} from '../api/agents';
import { fetchFundThesisSummary } from '../api/fundThesis';
import { getQueryConfig } from '../lib/queryIntent';
import { railEditorial } from '../design-system/railEditorial';
import {
  getBacklogPressure,
  isDealPendingPartnerDecision,
  isDealUnreviewed,
} from '../lib/dealState';
import type { FundConfiguration } from '../lib/fundConfiguration';

const SYSTEM_MEMO_HEADER_PADDING = 'py-phi-3';
const SETTINGS_PATH = '/v1/settings';

const PANEL_CHROME_ACTION_BTN_CLASS =
  `${UI_PANEL_CHROME_LABEL} rounded-none border-0 bg-transparent p-0 cursor-pointer hover:text-oxford/80 transition-colors duration-150 ease-out btn-interaction focus:outline-none focus-visible:ring-2 focus-visible:ring-oxford/40 focus-visible:ring-inset`;

/** Memo sheet header actions — same inactive styling as WorkGrid source `FilterButton`. */
const MEMO_SHEET_ACTION_BTN_CLASS =
  'type-meta uppercase tracking-[0.12em] min-h-[36px] px-phi-3 transition-colors btn-interaction focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-oxford/35 text-oxford/40 hover:text-oxford/70';

type RailStageState = {
  key: string;
  label: string;
  enabled: boolean;
};

function PipelineHeaderSignal({
  stages,
  loopAlive,
  pipelineEnabled,
  issue,
}: {
  stages: RailStageState[];
  loopAlive: boolean;
  pipelineEnabled: boolean;
  issue: boolean;
}) {
  const statusLabel = issue ? 'Issue' : loopAlive ? 'Live' : pipelineEnabled ? 'Idle' : 'Paused';
  const statusTone = issue
    ? 'text-escalation'
    : loopAlive
      ? 'text-oxford/68'
      : pipelineEnabled
        ? 'text-oxford/44'
        : 'text-oxford/25';
  const showLiveDot = loopAlive && !issue;

  return (
    <div className="flex items-center gap-phi-2" aria-label="Pipeline and agent stage status">
      <span className="flex items-center gap-[3px]" aria-label="Enabled agent stages">
        {stages.map((stage) => {
          const active = stage.enabled && loopAlive && !issue;
          return (
            <span
              key={stage.key}
              className={`h-px w-[10px] shrink-0 ${
                active ? 'bg-oxford/58 pulse-soft' : stage.enabled ? 'bg-oxford/28' : 'bg-oxford/10'
              }`}
              title={`${stage.label} ${stage.enabled ? 'enabled' : 'off'}`}
              aria-label={`${stage.label} ${stage.enabled ? 'enabled' : 'off'}`}
            />
          );
        })}
      </span>
      <span className="flex items-center gap-phi-1.5" aria-live="polite">
        {showLiveDot ? (
          <span
            className="h-1.5 w-1.5 shrink-0 rounded-none bg-emerald-500 pulse-soft"
            aria-hidden
          />
        ) : null}
        <span className={`${railEditorial.statusLabel} ${statusTone}`}>
        {statusLabel}
        </span>
      </span>
    </div>
  );
}

interface MainLayoutProps {
  data: SystemData;
  startupsError?: string | null;
  onSystemPanelOpenChange?: (open: boolean) => void;
}

function EmptyMemoPressure({ startups, fundConfiguration }: { startups: Startup[]; fundConfiguration: FundConfiguration }) {
  const pressure = useMemo(() => getBacklogPressure(startups), [startups]);
  const oldestName = pressure.oldest?.startup.scout.name;
  const oldestAge = pressure.oldest?.ageDays;

  return (
    <div className="flex h-full min-h-0 items-center justify-center bg-paper px-phi-7 py-phi-7">
      <div className="w-full max-w-[34rem]">
        <p className="type-label-section tracking-[0.12em] text-oxford/45">Decision queue</p>
        <p className="mt-phi-3 font-display text-[1.9rem] font-medium leading-[0.98] tracking-0 text-oxford sm:text-[2.6rem]">
          Conviction queue requires review.
        </p>
        <dl className="mt-phi-6 grid grid-cols-3 gap-x-phi-5 gap-y-phi-4 border-y border-oxford/[0.08] py-phi-4">
          <div>
            <dt className="type-meta text-oxford/35">Pending</dt>
            <dd className="mt-phi-1 font-mono text-[1.35rem] font-semibold leading-none text-oxford tabular-nums">
              {pressure.pendingCount}
            </dd>
          </div>
          <div>
            <dt className="type-meta text-oxford/35">Adverse</dt>
            <dd className={`mt-phi-1 font-mono text-[1.35rem] font-semibold leading-none tabular-nums ${pressure.adverseCount > 0 ? 'text-escalation/80' : 'text-oxford'}`}>
              {pressure.adverseCount}
            </dd>
          </div>
          <div>
            <dt className="type-meta text-oxford/35">Oldest</dt>
            <dd className="mt-phi-1 font-mono text-[1.35rem] font-semibold leading-none text-oxford tabular-nums">
              {oldestAge != null && oldestAge >= 0 ? `${oldestAge}d` : '—'}
            </dd>
          </div>
        </dl>
        <div className="mt-phi-4 grid gap-phi-2 border-b border-oxford/[0.06] pb-phi-4">
          <p className="type-meta text-oxford/38">
            Stale threshold <span className="font-mono tabular-nums text-oxford/62">{fundConfiguration.thresholds.staleAfterHours}h</span>
          </p>
          <p className="type-meta text-oxford/38">
            Risk posture <span className="text-oxford/62">{fundConfiguration.risk.sensitivity}</span>
          </p>
        </div>
        <p className="mt-phi-4 type-meta leading-relaxed text-oxford/42">
          {oldestName && oldestAge != null && oldestAge >= 0
            ? `${oldestName} is the oldest unresolved matter in the queue.`
            : 'Select a matter to inspect the current ruling surface.'}
        </p>
      </div>
    </div>
  );
}

export default function MainLayout({
  data,
  startupsError,
  onSystemPanelOpenChange,
}: MainLayoutProps) {
  const { configuration: fundConfiguration } = useFundConfiguration(data.settings);
  const {
    startups,
    signals,
    metaReports,
    rejectionAnalytics,
    watchlistAnalytics,
    concentrationAnalytics,
    scoutWeights,
    calibrationState,
    metaPromptState,
    metaEvalSet,
    systemHealth,
    metaInsights,
    liveGate,
  } = data;
  const [selectedStartup, setSelectedStartup] = useState<Startup | null>(null);
  const [rightPanel, setRightPanel] = useState<'memo' | 'feed' | 'system' | null>(null);
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

  const handleDecisionResolved = useCallback((nextStartup: Startup) => {
    queryClient.setQueryData<Startup[]>(['startups', 'list'], (prev) =>
      prev?.map((s) => (s.id === nextStartup.id ? nextStartup : s)) ?? prev
    );
    queryClient.setQueryData<Startup | null>(['startup', 'detail', nextStartup.id], nextStartup);
    setSelectedStartup((current) => (current?.id === nextStartup.id ? nextStartup : current));
    void queryClient.invalidateQueries({ queryKey: ['escalations'] });
    void queryClient.invalidateQueries({ queryKey: ['settings'] });
  }, [queryClient]);

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

  const openInProgressCount =
    startups.filter(isDealUnreviewed).length + startups.filter(isDealPendingPartnerDecision).length;
  const decidedCount = startups.filter((startup) => Boolean(startup.partner?.recommendation)).length;
  const pendingEscalations = data.pendingEscalationCount ?? data.settings?.system_health?.pending_escalations ?? 0;
  const agentConfig = data.settings?.agent_config;
  const pipelineEnabled =
    !!agentConfig && !!(agentConfig.scouts_enabled || agentConfig.reviewers_enabled || agentConfig.partners_enabled);
  const lookupWorking = lookupBusy || (pendingLookup != null && !pendingLookup.autoOpened);

  const { data: agentsStatus } = useQuery({
    queryKey: ['agents-status'],
    queryFn: () => fetchAgentsStatus().catch(() => null),
    ...getQueryConfig('SEMI_DYNAMIC', { liveGate }),
  });

  const { data: loopStatus } = useQuery({
    queryKey: ['agents-loop-status'],
    queryFn: () => fetchLoopStatus().catch(() => null),
    ...getQueryConfig('SEMI_DYNAMIC', { liveGate, pollIntervalMs: 30_000 }),
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
  const pipelineLoopAlive = Boolean(loopStatus?.loop_alive);
  const pipelineStages: RailStageState[] = [
    { key: 'scout', label: 'Scout', enabled: Boolean(agentConfig?.scouts_enabled) },
    { key: 'review', label: 'Review', enabled: Boolean(agentConfig?.reviewers_enabled) },
    { key: 'partner', label: 'Partner', enabled: Boolean(agentConfig?.partners_enabled) },
  ];
  useEffect(() => {
    onSystemPanelOpenChange?.(rightPanel === 'system');
  }, [rightPanel, onSystemPanelOpenChange]);

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
    // Fall back to settings if parsed_json has nothing — chips are sectors · stage · region only
    return {
      sectors,
      stages: stages.length ? stages : fundStage ? [fundStage] : [],
      geos: geos.length ? geos : fundGeo ? [fundGeo] : scoutRegion ? [scoutRegion] : [],
    };
  }, [fundThesisSummary, fundStage, fundGeo, scoutRegion]);
  const thesisTagList = useMemo(
    () => [...thesisTags.stages, ...thesisTags.geos, ...thesisTags.sectors],
    [thesisTags.geos, thesisTags.sectors, thesisTags.stages]
  );
  const hasThesisTags = thesisTagList.length > 0;

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
                className="border-b border-white/[0.08] type-label-tab bg-oxford text-white/72"
                aria-label="Menu"
              >
                <div className="px-phi-4 pb-0">
                  <div className="flex flex-col items-start gap-phi-3 py-phi-3">
                    {/* Mode toggles: Deals / Judgements / System — same mono scale as desktop spine */}
                    <div className="flex flex-col items-stretch gap-phi-1 w-full">
                      <button
                        type="button"
                        onClick={() => {
                          setRightPanel((panel) => (panel === 'feed' ? null : 'feed'));
                          setMobileMenuOpen(false);
                        }}
                        className={`type-label-tab min-h-[44px] flex items-center justify-start cursor-pointer px-1 btn-interaction ${rightPanel === 'feed' ? 'text-white' : 'text-white/60 hover:text-white'
                          }`}
                        style={{ transitionTimingFunction: 'var(--motion-ease)' }}
                        aria-pressed={rightPanel === 'feed'}
                      >
                        <span
                          className={`inline-block px-2 py-1 ${rightPanel === 'feed' ? 'bg-white/[0.07]' : 'hover:bg-white/[0.05]'}`}
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
                        className={`type-label-tab min-h-[44px] flex items-center justify-start cursor-pointer px-1 btn-interaction ${rightPanel !== 'system' && rightPanel !== 'feed'
                          ? 'text-white'
                          : 'text-white/60 hover:text-white'
                          }`}
                        style={{ transitionTimingFunction: 'var(--motion-ease)' }}
                        aria-pressed={rightPanel !== 'system' && rightPanel !== 'feed'}
                      >
                        <span
                          className={`inline-block px-2 py-1 ${rightPanel !== 'system' && rightPanel !== 'feed' ? 'bg-white/[0.07]' : 'hover:bg-white/[0.05]'}`}
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
                        className={`type-label-tab min-h-[44px] flex items-center justify-start cursor-pointer px-1 btn-interaction ${rightPanel === 'system' ? 'text-white' : 'text-white/60 hover:text-white'
                          }`}
                        style={{ transitionTimingFunction: 'var(--motion-ease)' }}
                        aria-pressed={rightPanel === 'system'}
                      >
                        <span
                          className={`inline-block px-2 py-1 ${rightPanel === 'system' ? 'bg-white/[0.07]' : 'hover:bg-white/[0.05]'}`}
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

      {startupsError && (
        <div className="flex-none px-6 py-2 bg-warning border-b border-oxford/25 type-label-tab text-oxford">
          {startupsError} — Check API URL (VITE_API_URL) and backend CORS (ALLOWED_ORIGINS).
        </div>
      )}

      <main className="flex-1 flex min-h-0 overflow-hidden bg-paper">
        <div
          className="w-4 shrink-0 self-stretch origin-top sm:w-7 md:w-10"
          style={{ backgroundColor: 'var(--color-oxford)' }}
          aria-hidden="true"
        />
        <div className="flex-1 flex flex-col min-h-0 min-w-0 overflow-hidden bg-paper pl-phi-3 pr-phi-5 pt-phi-4 pb-phi-5 lg:pl-phi-3 lg:pr-phi-5 lg:pt-phi-5 lg:pb-phi-5">
          <div className="flex-1 flex flex-col lg:grid lg:grid-cols-[minmax(240px,0.8fr)_minmax(460px,1.2fr)_minmax(0,1.4fr)] lg:grid-rows-[minmax(0,1fr)] min-h-0 overflow-hidden gap-phi-5 lg:gap-phi-5 bg-paper">
            <aside className="paper-dot-grid hidden lg:flex h-full min-h-0 max-h-full min-w-0 flex-col overflow-hidden">
              <div className="paper-dot-grid flex h-full min-h-0 flex-col justify-between overflow-hidden px-phi-4" style={{ paddingTop: 'clamp(5px, 0.6vw, 8px)', paddingBottom: 'clamp(5px, 0.6vw, 8px)' }}>

                {/* ── Wordmark + pipeline status ─────────────────────── */}
                <div className="min-w-0">
                  <div className="flex items-center justify-between gap-phi-3">
                    <p className={railEditorial.wordmark}>
                      Aethria
                    </p>
                    <div className="relative flex items-center gap-phi-2">
                      <PipelineHeaderSignal
                        stages={pipelineStages}
                        loopAlive={pipelineLoopAlive}
                        pipelineEnabled={pipelineEnabled}
                        issue={pipelineHealthIssue}
                      />
                      {pipelineStateLabel === 'Issue' && (
                        <>
                          <button
                            type="button"
                            onClick={() => setShowPipelineIssueHelp((open) => !open)}
                            className="inline-flex h-3.5 w-3.5 shrink-0 items-center justify-center rounded-none border border-escalation/40 type-meta leading-none text-escalation hover:bg-escalation/10 btn-interaction focus:outline-none focus-visible:ring-2 focus-visible:ring-escalation/40"
                            aria-label="Pipeline issue details"
                            aria-expanded={showPipelineIssueHelp}
                          >
                            ?
                          </button>
                          {showPipelineIssueHelp && (
                            <span className="absolute right-0 top-[calc(100%+8px)] z-20 w-56 border border-field-border bg-paper p-phi-3 text-left normal-case tracking-normal type-label-section leading-phi text-oxford">
                              Pipeline has a problem and may not process updates right now.
                              <button
                                type="button"
                                onClick={() => navigate(SETTINGS_PATH)}
                                className="mt-phi-2 block type-meta text-oxford/35 hover:text-oxford btn-interaction"
                              >
                                Open settings →
                              </button>
                            </span>
                          )}
                        </>
                      )}
                    </div>
                  </div>

                  {/* Nav */}
                  <div className="mt-phi-3 -mx-phi-4">
                    <SystemBar
                      variant="embedded"
                      rightPanel={rightPanel}
                      onShowDeals={() => setRightPanel((p) => (p === 'system' ? null : p))}
                      onShowFeed={() => setRightPanel((panel) => (panel === 'feed' ? null : 'feed'))}
                      onShowSystem={() => setRightPanel((panel) => (panel === 'system' ? null : 'system'))}
                      onClose={() => setRightPanel(null)}
                    />
                  </div>
                </div>

                {/* ── Dispatch (on-demand lookup) ─────────────────────── */}
                <div className="min-w-0 border-t border-oxford/[0.075]" style={{ paddingTop: 'clamp(5px, 0.6vw, 8px)' }}>
                  <p className={railEditorial.label}>Dispatch</p>
                  <div className="mt-phi-2 min-w-0">
                  <AgentDispatch
                    input={lookupInput}
                    setInput={setLookupInput}
                    onSubmit={() => void handleLookupSubmit()}
                    isBusy={lookupBusy}
                    message={lookupMessage}
                    onClearMessage={() => setLookupMessage(null)}
                    lookupPhase={lookupPhaseLabel}
                    alwaysOpen
                  />
                  </div>
                </div>

                {/* ── Overview ───────────────────────────────────────── */}
                <section aria-label="Live overview" className="min-w-0 border-t border-oxford/[0.075]" style={{ paddingTop: 'clamp(5px, 0.6vw, 8px)' }}>
                  <p className={railEditorial.label}>Overview</p>
                  <div className="grid min-w-0 grid-cols-2" style={{ columnGap: 'clamp(8px, 1vw, 13px)', rowGap: 'clamp(5px, 0.8vw, 8px)' }}>
                    {[
                      { label: 'Total', value: startups.length, accent: false },
                      { label: 'Open/in-progress', value: openInProgressCount, accent: false },
                      { label: 'Decided', value: decidedCount, accent: false },
                      { label: 'Escalated', value: pendingEscalations, accent: pendingEscalations > 0 },
                    ].map((stat) => (
                      <div
                        key={stat.label}
                        className="flex min-h-0 min-w-0 flex-col justify-between gap-phi-2"
                      >
                        <span className={railEditorial.statLabel}>{stat.label}</span>
                        <span
                          className={`${railEditorial.statValue} truncate ${stat.accent ? 'text-escalation' : 'text-oxford'}`}
                        >
                          {stat.value.toLocaleString()}
                        </span>
                      </div>
                    ))}
                  </div>
                </section>

                {/* ── Mandate ────────────────────────────────────────── */}
                <article className="min-w-0 overflow-hidden border-t border-oxford/[0.075]" style={{ paddingTop: 'clamp(5px, 0.6vw, 8px)' }} aria-label="Fund thesis preview">
                  <p className={railEditorial.label}>Mandate</p>
                  <div className="flex min-w-0 items-center justify-between gap-phi-3">
                    <p className={`min-w-0 flex-1 truncate ${railEditorial.bodyStrong}`}>
                      {fundName || 'No fund configured'}
                    </p>
                    {hasThesis ? (
                      <div
                        className="flex shrink-0 items-center gap-phi-2"
                        aria-live="polite"
                        title="Active mandate linked to pipeline"
                      >
                        <span
                          className="h-1.5 w-1.5 shrink-0 rounded-none bg-oxford signal-dot-breathe"
                          aria-hidden
                        />
                        <span
                          className={`${railEditorial.meta} uppercase text-oxford/45 pulse-soft [animation-delay:900ms]`}
                        >
                          Live
                        </span>
                      </div>
                    ) : null}
                  </div>
                  {hasThesisTags && (
                    <div className="mt-phi-3 flex max-h-[4.9rem] flex-wrap gap-phi-2 overflow-hidden">
                      {thesisTagList.map((t, i) => (
                        <span
                          key={`mandate-${i}-${t}`}
                          className={`bg-registerTint px-phi-2 py-phi-1 ${railEditorial.meta} text-oxford/45`}
                        >
                          {t}
                        </span>
                      ))}
                    </div>
                  )}
                </article>

                {/* ── Account ─────────────────────────────────────────── */}
                <div className="min-w-0 border-t border-oxford/[0.075]" style={{ paddingTop: 'clamp(5px, 0.6vw, 8px)' }}>
                  <AccountRailPanel settingsPath={SETTINGS_PATH} />
                </div>

              </div>
            </aside>


            <div className="flex min-h-0 min-w-0 flex-1 flex-col bg-paper lg:h-full lg:min-h-0">
              {/* Pipeline summary + lookup */}
              <header className="flex-none mb-phi-5 min-w-0 lg:mb-0 lg:px-0">
                <section
                  aria-label="Pipeline summary and agent status"
                  className="grid min-w-0 grid-cols-1 gap-phi-4 pb-phi-4 px-phi-2 xl:grid-cols-[minmax(0,1fr)_auto] xl:items-end xl:gap-x-phi-5 lg:hidden"
                >
                  <div className="min-w-0 flex flex-col gap-phi-2">
                    <p className="type-meta text-oxford/30">Live overview</p>
                    <p className="type-meta text-oxford/60">
                      {startups.length} total · {openInProgressCount} open/in-progress · {decidedCount} decided · {pendingEscalations} escalated
                      {signals.length > 0 ? ` · ${signals.length} signals` : ''}
                    </p>
                  </div>
                  <div className="relative flex min-w-0 flex-col items-start gap-y-phi-1 xl:items-end">
                    <div className="flex min-w-0 flex-wrap items-baseline gap-x-phi-3 gap-y-phi-1 xl:justify-end">
                      <span className="type-meta text-oxford/30">Pipeline</span>
                      <span className="relative inline-flex items-center gap-phi-2">
                        {pipelineStateLabel === 'On' && (
                          <span
                            className="h-1.5 w-1.5 shrink-0 rounded-none bg-oxford/60 pulse-soft"
                            aria-hidden
                          />
                        )}
                        <span className={
                          pipelineStateLabel === 'Issue' ? 'type-meta text-escalation' :
                            pipelineStateLabel === 'Off' ? 'type-meta text-oxford/30' :
                              'type-meta text-oxford/60'
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
                                  className="mt-phi-2 block type-meta text-oxford/30 hover:text-oxford btn-interaction"
                                >
                                  Open settings →
                                </button>
                              </span>
                            )}
                          </>
                        )}
                      </span>
                    </div>
                    {pendingEscalations > 0 && (
                      <span className="type-meta text-escalation/85">
                        {pendingEscalations} escalation{pendingEscalations === 1 ? '' : 's'}
                      </span>
                    )}
                  </div>
                </section>
                <div className="pt-phi-1 lg:hidden">
                  <AgentDispatch
                    input={lookupInput}
                    setInput={setLookupInput}
                    onSubmit={() => void handleLookupSubmit()}
                    isBusy={lookupBusy}
                    message={lookupMessage}
                    onClearMessage={() => setLookupMessage(null)}
                    lookupPhase={lookupPhaseLabel}
                  />
                </div>
              </header>

              {/* Fund thesis — mobile only (desktop shows it in the right column) */}
              <div className="flex-none mb-phi-4 block lg:hidden">
                <article
                  className="w-full bg-paper px-phi-5 py-phi-4"
                  style={{ boxSizing: 'border-box' }}
                  aria-label="Fund thesis preview"
                >
                  <p className={railEditorial.label}>Active mandate</p>
                  <div className="flex min-w-0 items-center justify-between gap-phi-3">
                    <p className={`min-w-0 flex-1 truncate ${railEditorial.bodyStrong}`}>
                      {fundName || 'No fund configured'}
                    </p>
                    {hasThesis ? (
                      <div
                        className="flex shrink-0 items-center gap-phi-2"
                        aria-live="polite"
                        title="Active mandate linked to pipeline"
                      >
                        <span
                          className="h-1.5 w-1.5 shrink-0 rounded-none bg-oxford signal-dot-breathe"
                          aria-hidden
                        />
                        <span
                          className={`${railEditorial.meta} uppercase text-oxford/45 pulse-soft [animation-delay:900ms]`}
                        >
                          Live
                        </span>
                      </div>
                    ) : null}
                  </div>
                  {hasThesisTags && (
                    <div className="mt-phi-3 flex flex-wrap gap-phi-2">
                      {thesisTagList.map((t, i) => (
                        <span
                          key={`mandate-mobile-${i}-${t}`}
                          className={`px-phi-2 py-phi-1 ${railEditorial.meta} text-oxford/45 bg-registerTint`}
                        >
                          {t}
                        </span>
                      ))}
                    </div>
                  )}
                </article>
              </div>

              <div
                className="flex-1 min-h-0 overflow-y-auto overscroll-contain w-full min-w-0 rounded-none bg-paper"
                style={{ scrollbarGutter: 'stable' }}
              >
                {rightPanel === 'system' ? (
                  <SystemIntelligence
                    startups={startups}
                    signals={signals}
                    rejectionAnalytics={rejectionAnalytics}
                    watchlistAnalytics={watchlistAnalytics}
                    concentrationAnalytics={concentrationAnalytics}
                    systemHealth={systemHealth}
                    metaReports={metaReports}
                    scoutWeights={scoutWeights}
                    calibrationState={calibrationState}
                    metaPromptState={metaPromptState}
                    metaEvalSet={metaEvalSet}
                    metaInsights={metaInsights}
                    fundConfiguration={fundConfiguration}
                  />
                ) : (
                  <GhostTransition disableLift className="w-full min-w-0">
                    <WorkGrid
                      startups={startups}
                      onStartupClick={handleStartupClick}
                      selectedId={selectedStartup?.id ?? null}
                      watchlistIds={watchlistIds}
                      fundConfiguration={fundConfiguration}
                    />
                  </GhostTransition>
                )}
              </div>
            </div>

            {/* Right zone: Judgements or memo only — never System. */}
            <div className="hidden min-h-0 min-w-0 flex-col bg-paper lg:flex lg:h-full">
              <aside
                className="min-w-0 min-h-0 flex-1 bg-paper overflow-hidden"
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
                        className="min-h-0 flex-1 bg-surface-canvas"
                        title="Judgements"
                        titleClassName={UI_PANEL_CHROME_LABEL}
                        headerPaddingClass={SYSTEM_MEMO_HEADER_PADDING}
                        actions={
                          <button
                            type="button"
                            onClick={handleCloseJudgements}
                            className={PANEL_CHROME_ACTION_BTN_CLASS}
                            aria-label="Hide judgements"
                          >
                            Close
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
                        className="min-h-0 min-w-0 flex-1 w-full bg-paper"
                        title=""
                        showTitle={false}
                        headerPaddingClass={SYSTEM_MEMO_HEADER_PADDING}
                        headerBorderClass=""
                        headerJustifyClass="justify-end"
                        actions={
                          <div className="flex min-h-[36px] items-center gap-0" role="group" aria-label="Memo controls">
                            <button
                              type="button"
                              onClick={() => memoContentRef.current?.downloadPDF()}
                              className={MEMO_SHEET_ACTION_BTN_CLASS}
                              aria-label="Download IC pack as PDF"
                            >
                              IC pack (PDF)
                            </button>
                            <button
                              type="button"
                              onClick={() => memoContentRef.current?.downloadMarkdown()}
                              className={MEMO_SHEET_ACTION_BTN_CLASS}
                              aria-label="Download IC pack as Markdown"
                            >
                              IC pack (MD)
                            </button>
                            <button
                              type="button"
                              onClick={handleCloseMemo}
                              className={MEMO_SHEET_ACTION_BTN_CLASS}
                              aria-label="Close memo"
                            >
                              Close
                            </button>
                          </div>
                        }
                        contentClassName="memoShellContent bg-paper px-phi-4 py-phi-3 sm:px-phi-5 sm:py-phi-4"
                      >
                        {/*
                          Enter-only when swapping deals: `mode="wait"` on AnimatePresence forced a full
                          exit (~0.4s) before the next memo could mount — felt like stutter/jump.
                          Keyed motion.div remounts instantly; only the incoming memo fades in.
                        */}
                        <motion.div
                          key={memoStartup!.id}
                          initial={reduceMotion ? false : { opacity: 0, y: 6 }}
                          animate={{ opacity: 1, y: 0 }}
                          transition={transitionOrReduced(reduceMotion, {
                            duration: tokens.motion.duration.micro,
                            ease: tokens.motion.ease,
                          })}
                          className="h-full min-h-full bg-paper"
                        >
                          <InvestmentMemoContent
                            ref={memoContentRef}
                            startup={memoStartup!}
                            embedded
                            onMemoPipelineReady={handleMemoPipelineReady}
                            onDecisionResolved={handleDecisionResolved}
                            fundConfiguration={fundConfiguration}
                            peerStartups={startups}
                          />
                        </motion.div>
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
                      <EmptyMemoPressure startups={startups} fundConfiguration={fundConfiguration} />
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
              duration: tokens.motion.duration.long,
              ease: tokens.motion.easeDrawer,
            })}
            className="fixed top-0 right-0 w-full max-w-full sm:w-[380px] lg:w-[400px] z-[10000] flex flex-col bg-surface-canvas"
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
              title="Judgements"
              titleClassName={UI_PANEL_CHROME_LABEL}
              headerPaddingClass={SYSTEM_MEMO_HEADER_PADDING}
              actions={
                <button
                  type="button"
                  onClick={handleCloseJudgements}
                  className={`${PANEL_CHROME_ACTION_BTN_CLASS} min-w-[44px] min-h-[44px] flex items-center justify-center`}
                  aria-label="Close judgements panel"
                >
                  Close
                </button>
              }
              contentOverflowHidden
              contentClassName="flex-1 min-h-0 overflow-hidden"
              className="h-full bg-surface-canvas"
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
            fundConfiguration={fundConfiguration}
            peerStartups={startups}
          />
        )}
      </AnimatePresence>
    </div>
  );
}
