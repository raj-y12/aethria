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
import DispatchCommandBar from './DispatchCommandBar';
import LookupReadyToast from './LookupReadyToast';
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
import { productInteraction } from '../design-system/productSystem';
import type { Startup } from '../types/startup';
import type { SystemData } from '../hooks/useSystemData';
import InvestmentMemoContent, { type InvestmentMemoContentHandle } from './InvestmentMemoContent';
import { acknowledgeStartup, queueOnDemandLookup, fetchStartupDetail, fetchLookupJobStatus } from '../api/startups';
import {
  fetchAgentsStatus,
  fetchLoopStatus,
} from '../api/agents';
import { fetchFundThesisSummary } from '../api/fundThesis';
import { getQueryConfig } from '../lib/queryIntent';
import { buildMandateSummaryLine } from '../lib/railSummaries';
import { railEditorial } from '../design-system/railEditorial';
import { isDealHumanResolved, isDealUnresolved } from '../lib/dealState';
import { LookupResultSnapshot } from '@aethria/product-chrome';
import { buildLookupSnapshotProps } from '../lib/productChromeMappers';

const SETTINGS_PATH = '/v1/settings';

/** Set true to show lookup result card in the Dispatch rail. */
const SHOW_LOOKUP_RESULT_SNAPSHOT = false;

const PANEL_CHROME_ACTION_BTN_CLASS = productInteraction.panelAction;
const PANEL_CHROME_INLINE_ACTION_BTN_CLASS = productInteraction.panelActionInline;

type RailStageState = {
  key: string;
  label: string;
  enabled: boolean;
};

function SystemTelemetryRail({
  totalCount,
  openInProgressCount,
  agentDecidedCount,
  humanRuledCount,
  pendingEscalations,
  pipelineEnabled,
  pipelineLoopAlive,
  pipelineStopping,
  pipelineHealthIssue,
  stages,
  showIssueHelp,
  onToggleIssueHelp,
  onOpenSettings,
}: {
  totalCount: number;
  openInProgressCount: number;
  agentDecidedCount: number;
  humanRuledCount: number;
  pendingEscalations: number;
  pipelineEnabled: boolean;
  pipelineLoopAlive: boolean;
  pipelineStopping: boolean;
  pipelineHealthIssue: boolean;
  stages: RailStageState[];
  showIssueHelp: boolean;
  onToggleIssueHelp: () => void;
  onOpenSettings: () => void;
}) {
  const hasEscalations = pendingEscalations > 0;
  const primaryLabel = hasEscalations ? 'Escalations' : 'Open / in-progress';
  const primaryValue = hasEscalations ? pendingEscalations : openInProgressCount;
  const statusLabel = pipelineStopping
    ? 'STOPPING'
    : !pipelineEnabled
    ? 'OFF'
    : pipelineHealthIssue
      ? 'ISSUE'
      : pipelineLoopAlive
        ? 'LIVE'
        : 'IDLE';
  const statusTone = pipelineHealthIssue
    ? 'text-escalation'
    : pipelineStopping
      ? 'text-oxford/55'
    : !pipelineEnabled
      ? 'text-oxford/28'
      : pipelineLoopAlive
        ? 'text-oxford'
        : 'text-oxford/45';
  const statusDot = pipelineHealthIssue
    ? 'bg-escalation'
    : pipelineStopping
      ? 'bg-oxford/45 pulse-soft'
    : !pipelineEnabled
      ? 'bg-oxford/18'
      : pipelineLoopAlive
        ? 'bg-oxford signal-dot-breathe'
        : 'bg-oxford/35';
  const stageSummary = stages
    .filter((stage) => stage.enabled)
    .map((stage) => stage.label)
    .join(' · ');
  const pipelineStatusTitle = pipelineEnabled ? stageSummary || 'Pipeline status' : 'Pipeline status';

  return (
    <article
      className="flex min-w-0 flex-col gap-phi-3 border border-oxford/[0.08] px-phi-4 py-phi-3"
      aria-label="Pipeline overview"
    >
      {/* Hero indicator + pipeline status, one glanceable row */}
      <div className="relative flex items-end justify-between gap-phi-3">
        <div className="min-w-0">
          <p className="font-mono text-[10px] uppercase tracking-[0.12em] text-oxford/40">
            {primaryLabel}
          </p>
          <p
            className={`mt-phi-1 font-mono text-[clamp(1.75rem,3vw,2.5rem)] font-bold leading-none tracking-[-0.04em] tabular-nums ${hasEscalations ? 'text-escalation' : 'text-oxford'}`}
            aria-live="polite"
          >
            {primaryValue.toLocaleString()}
          </p>
        </div>
        <span
          className={`inline-flex shrink-0 items-center gap-phi-2 pb-px font-mono text-[11px] uppercase tracking-[0.10em] ${statusTone}`}
          title={pipelineStatusTitle}
        >
          <span className={`h-1.5 w-1.5 shrink-0 rounded-none ${statusDot}`} aria-hidden />
          {statusLabel}
          {pipelineHealthIssue ? (
            <button
              type="button"
              onClick={onToggleIssueHelp}
              className="ml-phi-1 inline-flex h-3.5 w-3.5 shrink-0 items-center justify-center rounded-none border border-escalation/40 font-mono text-[10px] leading-none text-escalation hover:text-escalation/75 btn-interaction focus:outline-none focus-visible:ring-2 focus-visible:ring-escalation/40"
              aria-label="Pipeline issue details"
              aria-expanded={showIssueHelp}
            >
              ?
            </button>
          ) : null}
        </span>
        {showIssueHelp && pipelineHealthIssue ? (
          <span className="absolute right-0 top-[calc(100%+8px)] z-20 w-56 border border-field-border bg-paper p-phi-3 text-left normal-case tracking-normal type-label-section leading-phi text-oxford shadow-sm">
            Pipeline has a problem and may not process updates right now.
            <button
              type="button"
              onClick={onOpenSettings}
              className="mt-phi-2 block type-meta text-oxford/35 hover:text-oxford btn-interaction"
            >
              Open settings →
            </button>
          </span>
        ) : null}
      </div>

      {/* Dense metric readout — all counts on one line */}
      <p className="border-t border-oxford/[0.075] pt-phi-3 font-mono text-[11px] tracking-[0.04em] tabular-nums text-oxford/45">
        <span className="font-semibold text-oxford">{totalCount.toLocaleString()}</span> total
        <span className="mx-phi-2 text-oxford/20" aria-hidden>·</span>
        <span className="font-semibold text-oxford">{agentDecidedCount.toLocaleString()}</span> rec
        <span className="mx-phi-2 text-oxford/20" aria-hidden>·</span>
        <span className="font-semibold text-oxford">{humanRuledCount.toLocaleString()}</span> ruled
      </p>
    </article>
  );
}

interface MainLayoutProps {
  data: SystemData;
  startupsError?: string | null;
  onSystemPanelOpenChange?: (open: boolean) => void;
}

function EmptyMemoPressure({ pendingEscalations }: { pendingEscalations: number }) {
  const hasEscalations = pendingEscalations > 0;
  const footnote = hasEscalations
    ? `${pendingEscalations.toLocaleString()} escalation${pendingEscalations === 1 ? '' : 's'} waiting — start with a flagged row.`
    : 'Pipeline counts are in the left rail.';

  return (
    <div className="flex h-full min-h-0 items-center justify-center bg-paper px-phi-7 py-phi-7">
      <article className="w-full max-w-[28rem]" aria-label="Conviction queue empty state">
        <p className="font-mono text-[10px] uppercase tracking-[0.12em] text-oxford/45">Conviction queue</p>
        <p className={`mt-phi-3 ${railEditorial.bodyStrong} leading-[1.25]`}>
          Select a matter from the queue to open the memo.
        </p>
        <p className={`mt-phi-3 ${railEditorial.meta} leading-relaxed text-oxford/36`}>{footnote}</p>
      </article>
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
    fundThesisRuntime,
    fundThesisRuntimeLoading,
    fundThesisRuntimeError,
    liveGate,
  } = data;
  const [selectedStartup, setSelectedStartup] = useState<Startup | null>(null);
  const [rightPanel, setRightPanel] = useState<'feed' | 'system' | null>(null);
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
  const [commandBarOpen, setCommandBarOpen] = useState(false);
  const restoreRefVerdictMemo = useRef<HTMLElement | null>(null);
  const judgementsPanelRef = useRef<HTMLDivElement | null>(null);
  const memoContentRef = useRef<InvestmentMemoContentHandle | null>(null);
  const lookupRequestSeqRef = useRef(0);
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

  const markStartupAcknowledged = useCallback((startup: Startup) => {
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
      prev?.map((s) => (s.id === startup.id ? { ...s, ...optimistic } : s)) ?? prev
    );
    queryClient.setQueryData<Startup | null>(['startup', 'detail', startup.id], (prev) =>
      prev ? { ...prev, ...optimistic } : prev
    );
    setSelectedStartup((current) => (current?.id === startup.id ? { ...current, ...optimistic } : current));
    void acknowledgeStartup(startup.id).then((updated) => {
      if (!updated) return;
      queryClient.setQueryData<Startup[]>(['startups', 'list'], (prev) =>
        prev?.map((s) => (s.id === updated.id ? { ...s, ...updated } : s)) ?? prev
      );
      queryClient.setQueryData<Startup | null>(['startup', 'detail', updated.id], updated);
      setSelectedStartup((current) => (current?.id === updated.id ? updated : current));
    });
  }, [queryClient]);

  const handleStartupClick = useCallback((startup: Startup) => {
    restoreRefVerdictMemo.current = document.activeElement as HTMLElement | null;
    const acknowledgedStartup = startup.is_new_to_user
      ? {
          ...startup,
          is_new_to_user: false,
          timestamps: {
            ...(startup.timestamps ?? {}),
            acknowledged_at: startup.timestamps?.acknowledged_at ?? new Date().toISOString(),
            last_seen_by_user_at: new Date().toISOString(),
          },
        }
      : startup;
    setSelectedStartup(acknowledgedStartup);
    if (startup.is_new_to_user) markStartupAcknowledged(startup);
  }, [markStartupAcknowledged]);

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
  }, []);

  const handleCloseJudgements = useCallback(() => {
    setRightPanel((panel) => (panel === 'feed' ? null : panel));
  }, []);

  const handleLookupSubmit = useCallback(async () => {
    const value = lookupInput.trim();
    if (!value || lookupBusy || (pendingLookup != null && !pendingLookup.autoOpened)) return;
    const requestSeq = lookupRequestSeqRef.current + 1;
    lookupRequestSeqRef.current = requestSeq;
    setLookupBusy(true);
    setLookupMessage('Submitting lookup request...');
    try {
      const lookupId = crypto.randomUUID();
      const queued = await queueOnDemandLookup(value, lookupId);
      if (lookupRequestSeqRef.current !== requestSeq) return;
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
      if (lookupRequestSeqRef.current === requestSeq) setLookupBusy(false);
    }
  }, [lookupInput, lookupBusy, pendingLookup]);

  const handleLookupCancel = useCallback(() => {
    lookupRequestSeqRef.current += 1;
    setLookupBusy(false);
    setPendingLookup(null);
    setLookupMessage(null);
  }, []);

  // ⌘K / Ctrl+K opens the dispatch command bar from anywhere in the cockpit.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && (e.key === 'k' || e.key === 'K')) {
        e.preventDefault();
        setCommandBarOpen(true);
      }
    };
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, []);

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
        `Lookup complete: ${matched.scout.name} analyzed. Review the result and open the memo.`
      );
    } else if (matched.review) {
      setLookupMessage(
        `Found ${matched.scout.name}. Review is complete and the partner decision is now running...`
      );
    } else {
      setLookupMessage(`Found ${matched.scout.name}. Running analyst review and scoring...`);
    }
    // No silent auto-navigation: the takeover surfaces the result overview with an
    // "Open memo" action (handleOpenLookupMemo) so the user advances deliberately.
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

  const openInProgressCount = startups.filter(isDealUnresolved).length;
  const agentDecidedCount = startups.filter((startup) => Boolean(startup.partner?.recommendation) && !isDealHumanResolved(startup)).length;
  const humanRuledCount = startups.filter(isDealHumanResolved).length;
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
    (
      !agentsStatus.worker_ready ||
      !agentsStatus.supabase_configured ||
      !agentsStatus.openai_configured ||
      !agentsStatus.agents_will_run ||
      agentsStatus.thesis_ready === false
    );
  const pipelineStopping = Boolean(loopStatus?.loop_alive && loopStatus?.agents_enabled === false && !pipelineHealthIssue);
  const pipelineLoopAlive = Boolean(loopStatus?.loop_alive && agentsStatus?.agents_will_run === true && !pipelineHealthIssue);
  const pipelineStateLabel = pipelineStopping
    ? 'Stopping'
    : !pipelineEnabled
    ? 'Off'
    : pipelineHealthIssue
      ? 'Issue'
      : pipelineLoopAlive
        ? 'Live'
        : 'Idle';
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
    const pj = fundThesisSummary?.parsed_json;
    if (pj && typeof pj === 'object') {
      for (const key of ['fund_name', 'name', 'title', 'fund', 'fund_title']) {
        const val = (pj as Record<string, unknown>)[key];
        if (typeof val === 'string' && val.trim()) return val.trim();
      }
    }
    const settingsName = data.settings?.fund_identity?.fund_name?.trim();
    if (settingsName) return settingsName;
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
    const geos = pj
      ? toStrings(pj.geography ?? pj.geographies ?? pj.geographic_focus)
      : toStrings(undefined);
    return {
      sectors,
      stages: stages.length ? stages : fundStage ? [fundStage] : [],
      geos: geos.length ? geos : fundGeo ? [fundGeo] : scoutRegion ? [scoutRegion] : [],
    };
  }, [fundThesisSummary, fundStage, fundGeo, scoutRegion]);
  const thesisTagList = useMemo(
    () => [...thesisTags.stages, ...thesisTags.geos, ...thesisTags.sectors],
    [thesisTags.geos, thesisTags.sectors, thesisTags.stages],
  );
  const mandateSummaryLine = useMemo(
    () =>
      buildMandateSummaryLine({
        stages: thesisTags.stages,
        geos: thesisTags.geos,
        sectors: thesisTags.sectors,
      }),
    [thesisTags.geos, thesisTags.sectors, thesisTags.stages],
  );
  const desktopMandateLine = hasThesis
    ? mandateSummaryLine
    : 'No active thesis';
  const hasThesisTags = thesisTagList.length > 0;

  const lookupSnapshotProps = useMemo(() => {
    if (!pendingLookupMatch) return null;
    return buildLookupSnapshotProps(pendingLookupMatch, pendingLookup?.queryLabel);
  }, [pendingLookupMatch, pendingLookup?.queryLabel]);

  // In-flight lookup → drives the takeover's progressive reveal (null once decided).
  const lookupProgress = useMemo(() => {
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

  // A finished background lookup the analyst hasn't opened yet → "ready" toast.
  const lookupReady =
    !commandBarOpen && pendingLookup != null && !pendingLookup.autoOpened
      ? pendingLookupMatch?.partner?.recommendation
        ? pendingLookupMatch
        : null
      : null;

  const handleOpenLookupMemo = useCallback(() => {
    if (!pendingLookupMatch) return;
    const now = new Date().toISOString();
    setSelectedStartup({
      ...pendingLookupMatch,
      is_new_to_user: false,
      timestamps: {
        ...(pendingLookupMatch.timestamps ?? {}),
        acknowledged_at: pendingLookupMatch.timestamps?.acknowledged_at ?? now,
        last_seen_by_user_at: now,
      },
    });
    if (pendingLookupMatch.is_new_to_user) markStartupAcknowledged(pendingLookupMatch);
    setPendingLookup((prev) => (prev ? { ...prev, autoOpened: true } : prev));
    setCommandBarOpen(false); // close the takeover so the memo is visible
  }, [pendingLookupMatch, markStartupAcknowledged]);

  // Closing the takeover with a finished-but-unopened lookup clears it so the
  // next lookup isn't blocked by the in-flight guard.
  const handleCloseDispatch = useCallback(() => {
    setCommandBarOpen(false);
    setPendingLookup((prev) => (prev && !prev.autoOpened && pendingLookupMatch ? null : prev));
  }, [pendingLookupMatch]);

  return (
    <div className="h-[100dvh] flex flex-col overflow-hidden bg-paper">
      <DispatchCommandBar
        open={commandBarOpen}
        onClose={handleCloseDispatch}
        input={lookupInput}
        setInput={setLookupInput}
        onSubmit={() => void handleLookupSubmit()}
        onCancel={handleLookupCancel}
        isBusy={lookupWorking}
        message={lookupMessage}
        onClearMessage={() => setLookupMessage(null)}
        lookupPhase={lookupPhaseLabel}
        progress={lookupProgress}
        result={
          pendingLookupMatch?.partner?.recommendation && lookupSnapshotProps ? (
            <LookupResultSnapshot {...lookupSnapshotProps} onOpenMemo={handleOpenLookupMemo} />
          ) : null
        }
      />
      <LookupReadyToast
        name={lookupReady?.scout?.name ?? null}
        recommendation={lookupReady?.partner?.recommendation ?? null}
        onOpen={handleOpenLookupMemo}
        onDismiss={() => setPendingLookup((prev) => (prev ? { ...prev, autoOpened: true } : prev))}
      />
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
          <div className="flex-1 flex min-h-0 flex-col overflow-hidden bg-paper lg:grid aethria-workspace-grid">
            <aside className="aethria-workspace-sidebar paper-dot-grid hidden lg:flex h-full min-h-0 max-h-full min-w-0 flex-col overflow-hidden">
              <div className="paper-dot-grid flex h-full min-h-0 flex-col justify-between overflow-hidden px-phi-4" style={{ paddingTop: 'clamp(5px, 0.6vw, 8px)', paddingBottom: 'clamp(5px, 0.6vw, 8px)' }}>

                {/* ── Wordmark + pipeline status ─────────────────────── */}
                <div className="min-w-0">
                  <div className="flex items-center justify-between gap-phi-3">
                    <p className={railEditorial.wordmark}>
                      Aethria
                    </p>
                  </div>

                  {/* Nav */}
                  <div className="mt-phi-3 aethria-rail-nav-bleed">
                    <SystemBar
                      variant="embedded"
                      rightPanel={rightPanel}
                      onShowDeals={() => setRightPanel((p) => (p === 'system' ? null : p))}
                      onShowFeed={() => setRightPanel((panel) => (panel === 'feed' ? null : 'feed'))}
                      onShowSystem={() => setRightPanel((panel) => (panel === 'system' ? null : 'system'))}
                      onClose={() => setRightPanel(null)}
                      onDispatch={() => setCommandBarOpen(true)}
                    />
                  </div>
                </div>

                {/* ── Pipeline overview ──────────────────────────────── */}
                <section aria-label="Pipeline overview" className="min-w-0" style={{ paddingTop: 'clamp(5px, 0.6vw, 8px)' }}>
                  <SystemTelemetryRail
                    totalCount={startups.length}
                    openInProgressCount={openInProgressCount}
                    agentDecidedCount={agentDecidedCount}
                    humanRuledCount={humanRuledCount}
                    pendingEscalations={pendingEscalations}
                    pipelineEnabled={pipelineEnabled}
                    pipelineLoopAlive={pipelineLoopAlive}
                    pipelineStopping={pipelineStopping}
                    pipelineHealthIssue={pipelineHealthIssue}
                    stages={pipelineStages}
                    showIssueHelp={showPipelineIssueHelp}
                    onToggleIssueHelp={() => setShowPipelineIssueHelp((open) => !open)}
                    onOpenSettings={() => navigate(SETTINGS_PATH)}
                  />
                </section>


                {/* ── Mandate (single status pill) ─────────────────────── */}
                <button
                  type="button"
                  onClick={() => navigate(SETTINGS_PATH)}
                  className="group flex w-full min-w-0 items-center gap-phi-2 border-t border-oxford/[0.075] text-left focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-oxford/30"
                  style={{ paddingTop: 'clamp(5px, 0.6vw, 8px)' }}
                  title={mandateSummaryLine || desktopMandateLine || undefined}
                  aria-label={hasThesis ? `Active mandate: ${fundName || 'configured'} — open settings` : 'No active thesis — open settings'}
                >
                  <span
                    className={`h-1.5 w-1.5 shrink-0 rounded-none ${hasThesis ? 'bg-oxford signal-dot-breathe' : 'bg-oxford/25'}`}
                    aria-hidden
                  />
                  <span className={`min-w-0 flex-1 truncate ${railEditorial.bodyStrong} transition-colors group-hover:text-oxford`}>
                    {hasThesis ? (fundName || 'Active mandate') : 'No active thesis'}
                  </span>
                  <span className={`${railEditorial.meta} shrink-0 uppercase ${hasThesis ? 'text-oxford/40' : 'text-escalation/75'}`}>
                    {hasThesis ? 'Active' : 'Set up'}
                  </span>
                </button>

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
                      {startups.length} total · {openInProgressCount} open/in-progress · {agentDecidedCount} recs · {humanRuledCount} human-ruled · {pendingEscalations} need ruling
                      {signals.length > 0 ? ` · ${signals.length} signals` : ''}
                    </p>
                  </div>
                  <div className="relative flex min-w-0 flex-col items-start gap-y-phi-1 xl:items-end">
                    <div className="flex min-w-0 flex-wrap items-baseline gap-x-phi-3 gap-y-phi-1 xl:justify-end">
                      <span className="type-meta text-oxford/30">Pipeline</span>
                      <span className="relative inline-flex items-center gap-phi-2">
                        {pipelineStateLabel === 'Live' && (
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
                        {pendingEscalations} need human ruling
                      </span>
                    )}
                  </div>
                </section>
                <div className="pt-phi-1 lg:hidden">
                  <AgentDispatch
                    input={lookupInput}
                    setInput={setLookupInput}
                    onSubmit={() => void handleLookupSubmit()}
                    onCancel={handleLookupCancel}
                    isBusy={lookupWorking}
                    message={lookupMessage}
                    onClearMessage={() => setLookupMessage(null)}
                    lookupPhase={lookupPhaseLabel}
                  />
                  {SHOW_LOOKUP_RESULT_SNAPSHOT && lookupSnapshotProps ? (
                    <div className="mt-phi-3 min-w-0">
                      <LookupResultSnapshot {...lookupSnapshotProps} onOpenMemo={handleOpenLookupMemo} />
                    </div>
                  ) : null}
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
                    <p
                      className={`min-w-0 flex-1 truncate ${railEditorial.bodyStrong}`}
                      title={mandateSummaryLine || undefined}
                    >
                      {fundName || 'No fund configured'}
                    </p>
                    {hasThesis ? (
                      <div
                        className="flex shrink-0 items-center gap-phi-2"
                        aria-live="polite"
                        title="Active mandate used by the system"
                      >
                        <span
                          className="h-1.5 w-1.5 shrink-0 rounded-none bg-oxford signal-dot-breathe"
                          aria-hidden
                        />
                        <span
                          className={`${railEditorial.meta} uppercase text-oxford/45 pulse-soft [animation-delay:900ms]`}
                        >
                          Active
                        </span>
                      </div>
                    ) : null}
                  </div>
                  {hasThesisTags && (
                    <div className="mt-phi-3 flex flex-wrap gap-phi-2">
                      {thesisTagList.map((t, i) => (
                        <span
                          key={`mandate-mobile-${i}-${t}`}
                          className={`px-phi-2 py-phi-1 ${railEditorial.meta} text-oxford/32 bg-registerTint`}
                        >
                          {t}
                        </span>
                      ))}
                    </div>
                  )}
                </article>
              </div>

              <div
                className="flex-1 min-h-0 overflow-hidden w-full min-w-0 rounded-none bg-paper"
                style={{ scrollbarGutter: 'stable' }}
              >
                {rightPanel === 'system' ? (
                  <div className="h-full overflow-y-auto overscroll-contain">
                    <SystemIntelligence
                      startups={startups}
                      onStartupClick={handleStartupClick}
                      selectedStartupId={selectedStartup?.id ?? null}
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
                      fundThesisRuntime={fundThesisRuntime}
                      fundThesisRuntimeLoading={fundThesisRuntimeLoading}
                      fundThesisRuntimeError={fundThesisRuntimeError}
                      fundConfiguration={fundConfiguration}
                    />
                  </div>
                ) : (
                  <div className="h-full overflow-y-auto overscroll-contain">
                    <div className="min-h-full">
                      <GhostTransition disableLift className="w-full min-w-0 min-h-full">
                        <WorkGrid
                          startups={startups}
                          onStartupClick={handleStartupClick}
                          selectedId={selectedStartup?.id ?? null}
                          watchlistIds={watchlistIds}
                          fundConfiguration={fundConfiguration}
                        />
                      </GhostTransition>
                    </div>
                  </div>
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
                      ? 'Memo'
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
                        className="min-h-0 flex-1 bg-paper"
                        title="Judgements"
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
                        title="Memo"
                        headerClassName="!items-start !py-0 !pt-phi-2 !pb-phi-2 min-h-[46px]"
                        actions={
                          <div className="flex shrink-0 items-start gap-0" role="group" aria-label="Memo controls">
                            <button
                              type="button"
                              onClick={() => memoContentRef.current?.downloadPDF()}
                              className={PANEL_CHROME_INLINE_ACTION_BTN_CLASS}
                              aria-label="Download IC pack as PDF"
                            >
                              IC pack (PDF)
                            </button>
                            <button
                              type="button"
                              onClick={handleCloseMemo}
                              className={PANEL_CHROME_INLINE_ACTION_BTN_CLASS}
                              aria-label="Close memo"
                            >
                              Close
                            </button>
                          </div>
                        }
                        contentClassName="memoShellContent memoShellContent--workspace bg-paper px-phi-4 py-phi-3 sm:px-phi-5 sm:py-phi-4"
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
                            portfolioSignals={signals}
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
                      <EmptyMemoPressure pendingEscalations={pendingEscalations} />
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
              className="h-full bg-paper"
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
