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
import type { Startup, EscalationItem } from '../types/startup';
import type { SystemData } from '../hooks/useSystemData';
import InvestmentMemoContent, { type InvestmentMemoContentHandle } from './InvestmentMemoContent';
import { queueOnDemandLookup, fetchStartupDetail, fetchLookupJobStatus } from '../api/startups';
import { fetchAgentsStatus, type AgentsStatus } from '../api/agents';
import { fetchFundThesisSummary } from '../api/fundThesis';
import { getQueryConfig } from '../lib/queryIntent';

const SYSTEM_MEMO_HEADER_PADDING = 'py-[10px]';

const PANEL_CHROME_ACTION_BTN_CLASS =
  `${UI_PANEL_CHROME_LABEL} rounded-none border-0 bg-transparent p-0 cursor-pointer hover:text-oxford/80 transition-colors duration-150 ease-out btn-interaction focus:outline-none focus-visible:ring-2 focus-visible:ring-oxford/40 focus-visible:ring-inset`;

interface MainLayoutProps {
  data: SystemData;
  startupsError?: string | null;
  onSystemPanelOpenChange?: (open: boolean) => void;
}

export default function MainLayout({
  data,
  startupsError,
  onSystemPanelOpenChange,
}: MainLayoutProps) {
  const {
    startups,
    escalations,
    signals,
    metaReports,
    rejectionAnalytics,
    watchlistAnalytics,
    concentrationAnalytics,
    scoutWeights,
    calibrationState,
    liveGate,
  } = data;
  const [selectedStartup, setSelectedStartup] = useState<Startup | null>(null);
  const [rightPanel, setRightPanel] = useState<'memo' | 'feed' | 'system' | null>(null);
  const initialFirstMemoOpened = useRef(false);
  const [lookupExpanded, setLookupExpanded] = useState(false);
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

  const handleOpenEscalationMemo = useCallback(
    (esc: EscalationItem) => {
      const id = esc.startup_id ?? esc.id;
      const startup = startups.find((s) => s.id === id);
      if (!startup) return;
      restoreRefVerdictMemo.current = document.activeElement as HTMLElement | null;
      setSelectedStartup(startup);
      /* Leave rightPanel unchanged so System stays on the left; memo uses selectedStartup on the right. */
    },
    [startups]
  );

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
    setLookupMessage('Queueing lookup...');
    try {
      const lookupId = crypto.randomUUID();
      const queued = await queueOnDemandLookup(value, lookupId);
      setPendingLookup({
        lookupId: queued.lookupId,
        queryLabel: value,
        autoOpened: false,
      });
      setLookupMessage(`Queued lookup for ${queued.companyName}. Processing now...`);
      setLookupInput('');
    } catch {
      setLookupMessage('Failed to queue lookup. Please retry.');
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
    setLookupMessage(row.message ?? 'On-demand lookup could not be completed.');
    setPendingLookup(null);
  }, [pendingLookup, pendingLookupMatch, lookupFailureQuery.data]);

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
      setLookupMessage(`Processing ${pendingLookup.queryLabel}...`);
      return;
    }
    const hasDecision = !!matched.partner?.decision;
    if (hasDecision) {
      setLookupMessage(`Lookup complete: ${matched.scout.name}. Opening memo...`);
    } else if (matched.review) {
      setLookupMessage(`Found ${matched.scout.name}. Partner decision in progress...`);
    } else {
      setLookupMessage(`Found ${matched.scout.name}. Review in progress...`);
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

  const resolvedCount = startups.filter((s) => s.partner?.decision != null).length;
  const openCount = Math.max(0, startups.length - resolvedCount);
  const pendingEscalations = data.settings?.system_health?.pending_escalations ?? 0;
  const agentConfig = data.settings?.agent_config;
  const pipelineEnabled =
    !!agentConfig && !!(agentConfig.scouts_enabled || agentConfig.reviewers_enabled || agentConfig.partners_enabled);
  const lookupWorking = lookupBusy || (pendingLookup != null && !pendingLookup.autoOpened);

  const agentsQuery = useQuery({
    queryKey: ['agents', 'status'],
    queryFn: fetchAgentsStatus,
    staleTime: 60_000,
    refetchOnWindowFocus: false,
    refetchInterval: (q) => {
      if (!liveGate.tabVisible || !liveGate.userActive) return false;
      const d = q.state.data as AgentsStatus | undefined;
      const issue =
        !!d &&
        pipelineEnabled &&
        (!d.worker_ready || !d.supabase_configured || !d.openai_configured);
      return lookupWorking || issue ? 90_000 : false;
    },
  });
  const agentsStatus = agentsQuery.data ?? null;

  const fundThesisQuery = useQuery({
    queryKey: ['fund-thesis', 'summary'],
    queryFn: () => fetchFundThesisSummary().catch(() => null),
    ...getQueryConfig('STATIC'),
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
      : lookupWorking
        ? 'Working'
        : 'On';
  const lookupStateLabel = lookupWorking ? (lookupPhaseLabel ?? 'Working') : 'Idle';

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
  const thesisCriteria = useMemo(() => {
    const pj = fundThesisSummary?.parsed_json;
    const fromParsed: string[] = [];
    if (pj && typeof pj === 'object') {
      for (const key of ['stage', 'stage_focus', 'geography', 'geographic_focus', 'geographies', 'sectors', 'focus_areas', 'investment_criteria', 'themes', 'focus', 'sector']) {
        const val = (pj as Record<string, unknown>)[key];
        if (Array.isArray(val)) {
          for (const item of val) {
            if (typeof item === 'string' && item.trim()) { fromParsed.push(item.trim()); if (fromParsed.length >= 4) break; }
          }
        } else if (typeof val === 'string' && val.trim()) {
          fromParsed.push(val.trim());
        }
        if (fromParsed.length >= 4) break;
      }
    }
    const fromSettings = [fundStage, fundGeo, scoutRegion].filter(Boolean);
    // Prefer parsed thesis data; fill remaining slots from settings
    const combined = [...fromParsed, ...fromSettings];
    return combined.filter((v, i, arr) => arr.indexOf(v) === i).slice(0, 4);
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
                initial={{ opacity: 0, height: 0 }}
                animate={{ opacity: 1, height: 'auto' }}
                exit={{ opacity: 0, height: 0 }}
                transition={transitionOrReduced(reduceMotion, {
                  duration: tokens.motion.duration.micro,
                  ease: tokens.motion.ease,
                })}
                className="px-4 pb-0 border-b border-hairline type-label-tab bg-oxford overflow-hidden text-white/70"
                aria-label="Menu"
              >
                <div className="flex flex-col items-start gap-phi-3 py-phi-3">
                  {/* Mode toggles: Deals / Judgements / System — same mono scale as desktop spine */}
                  <div className="flex flex-col items-stretch gap-phi-1 w-full">
                    <button
                      type="button"
                      onClick={() => {
                        setRightPanel((panel) => (panel === 'feed' ? null : 'feed'));
                        setMobileMenuOpen(false);
                      }}
                      className={`type-meta min-h-[44px] flex items-center justify-start cursor-pointer px-0 uppercase tracking-[0.12em] btn-interaction ${
                        rightPanel === 'feed' ? 'text-white' : 'text-white/55 hover:text-white'
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
                      className={`type-meta min-h-[44px] flex items-center justify-start cursor-pointer px-0 uppercase tracking-[0.12em] btn-interaction ${
                        rightPanel !== 'system' && rightPanel !== 'feed'
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
                      className={`type-meta min-h-[44px] flex items-center justify-start cursor-pointer px-0 uppercase tracking-[0.12em] btn-interaction ${
                        rightPanel === 'system' ? 'text-white' : 'text-white/55 hover:text-white'
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
                  <a
                    href="/settings"
                    className="type-label-section text-white/70 hover:text-white btn-interaction"
                  >
                    Settings
                  </a>
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
        navLink={{ href: '/settings', label: 'Settings' }}
      />
      {startupsError && (
        <div className="flex-none px-6 py-2 bg-warning border-b border-oxford/25 type-label-tab text-oxford">
          {startupsError} — Check API URL (VITE_API_URL) and backend CORS (ALLOWED_ORIGINS).
        </div>
      )}

      {/* Paper canvas. Fixed height so only WorkGrid scrolls.
          On desktop content is offset to clear vertical SystemBar; on mobile it uses standard page padding. */}
      <main className="flex-1 flex flex-col min-h-0 overflow-hidden px-4 pt-3 lg:pl-[calc(9rem+21px)] lg:pr-[21px] lg:pt-[21px]">
        <div className="flex-1 flex flex-col lg:grid lg:grid-cols-[5fr_8fr] min-h-0 overflow-hidden pb-phi-3 lg:pb-phi-5 gap-phi-3 lg:gap-phi-5">
          <div className="flex min-w-0 min-h-0 flex-1 flex-col lg:min-h-0">
            {/* Pipeline summary + lookup */}
            <header className="flex-none mb-phi-3 min-w-0 lg:px-0">
              <section
                aria-label="Pipeline summary and agent status"
                className="border-b border-hairline pb-phi-3"
              >
                <div className="flex min-w-0 items-start justify-between gap-phi-4">
                  <div className="min-w-0 flex-1">
                    {fundName ? (
                      <p className="type-body font-semibold tracking-tight text-oxford leading-snug truncate">{fundName}</p>
                    ) : null}
                    {thesisCriteria.length > 0 ? (
                      <p className={`type-meta tracking-badge uppercase text-oxford/40 truncate ${fundName ? 'mt-phi-1' : ''}`}>
                        {thesisCriteria.join(' · ')}
                      </p>
                    ) : null}
                    <p className={`type-meta tracking-label uppercase text-oxford/40 ${(fundName || thesisCriteria.length > 0) ? 'mt-phi-2' : ''}`}>
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
                  </div>
                  <p className="shrink-0 text-right type-meta tracking-label uppercase text-oxford/40 pt-px">
                    Pipeline{' '}
                    <span className="relative inline-flex items-center gap-phi-2">
                      {/* Live dot — shown when pipeline is On or Working */}
                      {(pipelineStateLabel === 'On' || pipelineStateLabel === 'Working') && (
                        <span
                          className="h-1.5 w-1.5 shrink-0 rounded-none bg-oxford/60"
                          style={{ animation: pipelineStateLabel === 'On'
                            ? 'aethria-pulse 2.4s cubic-bezier(0.16,1,0.3,1) infinite'
                            : 'aethria-pulse 1.2s cubic-bezier(0.16,1,0.3,1) infinite'
                          }}
                          aria-hidden
                        />
                      )}
                      <span className={
                        pipelineStateLabel === 'Issue'   ? 'text-escalation' :
                        pipelineStateLabel === 'Off'     ? 'text-oxford/25' :
                        pipelineStateLabel === 'On'      ? 'text-oxford/80' :
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
                                onClick={() => navigate('/settings')}
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
                </div>
              </section>
              <div className="mt-phi-2 lg:mt-phi-3 min-w-0 border-l border-[var(--section-divider)] pl-phi-3 md:pl-phi-4">
                <button
                  type="button"
                  className="flex w-full min-w-0 items-center gap-phi-3 py-phi-2 text-left btn-interaction focus:outline-none focus-visible:ring-2 focus-visible:ring-oxford/35 focus-visible:ring-offset-2 focus-visible:ring-offset-paper"
                  aria-expanded={lookupExpanded}
                  aria-controls="lookup-panel"
                  onClick={() => setLookupExpanded((open) => !open)}
                >
                  <span className="shrink-0 type-meta tracking-label uppercase text-oxford/40">
                    Lookup
                  </span>
                  <span
                    className={`min-w-0 flex-1 truncate text-right type-meta tracking-badge uppercase ${
                      !lookupWorking
                        ? 'text-oxford/25'
                        : lookupPhaseLabel === 'Scouting'
                          ? 'text-oxford/60'
                          : lookupPhaseLabel === 'Reviewing'
                            ? 'text-oxford/80'
                            : 'text-oxford font-semibold'
                    }`}
                  >
                    {lookupStateLabel}
                  </span>
                  <span className="shrink-0 tabular-nums text-oxford/25" aria-hidden>
                    {lookupExpanded ? '−' : '+'}
                  </span>
                </button>
                <AnimatePresence initial={false}>
                  {lookupExpanded && (
                    <motion.div
                      id="lookup-panel"
                      initial={{ height: 0, opacity: 0 }}
                      animate={{ height: 'auto', opacity: 1 }}
                      exit={{ height: 0, opacity: 0 }}
                      transition={transitionOrReduced(reduceMotion, {
                        duration: tokens.motion.duration.micro,
                        ease: tokens.motion.ease,
                      })}
                      className="overflow-hidden"
                    >
                      <div className="pb-phi-2 pt-phi-1">
                        <p className="mb-phi-2 max-w-[42ch] type-body-sm leading-phi text-oxford/40">
                          Run the full pipeline on any company. Results appear in your queue when ready.
                        </p>
                        <div className="flex min-w-0 flex-col gap-phi-2 sm:flex-row sm:items-end sm:gap-phi-3">
                          <label className="min-w-0 flex-1">
                            <span className="sr-only">Company to look up</span>
                            <input
                              type="text"
                              value={lookupInput}
                              onChange={(e) => setLookupInput(e.target.value)}
                              onKeyDown={(e) => {
                                if (e.key === 'Enter') void handleLookupSubmit();
                              }}
                              placeholder="Company name or URL"
                              autoComplete="off"
                              className="h-9 w-full rounded-none border-0 border-b border-field-border bg-transparent px-0 type-body-sm text-oxford placeholder:text-oxford/25 outline-none focus:border-field-border-strong"
                            />
                          </label>
                          <button
                            type="button"
                            onClick={() => void handleLookupSubmit()}
                            disabled={lookupBusy || !lookupInput.trim()}
                            className="h-9 shrink-0 self-stretch px-0 type-meta tracking-label uppercase text-oxford/40 underline decoration-oxford/20 underline-offset-4 transition-colors hover:text-oxford hover:decoration-oxford/40 disabled:pointer-events-none disabled:text-oxford/25 disabled:no-underline btn-interaction sm:self-auto"
                          >
                            {lookupBusy ? 'Queueing…' : 'Run lookup'}
                          </button>
                        </div>
                        {lookupMessage ? (
                          <p className="mt-phi-2 type-meta leading-label text-oxford/40">{lookupMessage}</p>
                        ) : null}
                      </div>
                    </motion.div>
                  )}
                </AnimatePresence>
              </div>
            </header>


            {rightPanel === 'system' ? (
              <div className="flex min-h-0 flex-1 flex-col overflow-hidden w-full min-w-0 rounded-none border border-hairline bg-paper">
                <PanelShell
                  className="min-h-0 flex-1"
                  title="SYSTEM"
                  titleClassName={UI_PANEL_CHROME_LABEL}
                  headerPaddingClass={SYSTEM_MEMO_HEADER_PADDING}
                  headerBorderClass=""
                  actions={
                    <button
                      type="button"
                      onClick={() => setRightPanel(null)}
                      className={PANEL_CHROME_ACTION_BTN_CLASS}
                      aria-label="Hide system intelligence"
                    >
                      CLOSE
                    </button>
                  }
                  contentOverflowHidden
                  contentClassName="flex-1 min-h-0 overflow-hidden"
                >
                  <SystemIntelligence
                    signals={signals}
                    escalations={escalations}
                    rejectionAnalytics={rejectionAnalytics}
                    watchlistAnalytics={watchlistAnalytics}
                    concentrationAnalytics={concentrationAnalytics}
                    metaReports={metaReports}
                    scoutWeights={scoutWeights}
                    calibrationState={calibrationState}
                    onOpenEscalationMemo={handleOpenEscalationMemo}
                  />
                </PanelShell>
              </div>
            ) : (
              <div
                className="flex-1 min-h-0 overflow-y-auto overscroll-contain w-full min-w-0 rounded-none bg-paper"
                style={{ scrollbarGutter: 'stable both-edges' }}
              >
                <GhostTransition disableLift>
                  <WorkGrid
                    startups={startups}
                    onStartupClick={handleStartupClick}
                    selectedId={selectedStartup?.id ?? null}
                    watchlistIds={watchlistIds}
                  />
                </GhostTransition>
              </div>
            )}
          </div>

          {/* Right zone: Judgements or memo only — never System. */}
          <div className="hidden lg:flex min-w-0 min-h-0 flex-col">
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
              {rightPanel === 'feed' ? (
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
              ) : selectedStartup ? (
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
                <InvestmentMemoContent
                  key={memoStartup!.id}
                  ref={memoContentRef}
                  startup={memoStartup!}
                  embedded
                  onMemoPipelineReady={handleMemoPipelineReady}
                />
              </PanelShell>
              ) : (
              <div className="flex-1 flex flex-col items-center justify-center gap-phi-3 p-8 select-none">
                <p className="font-display font-normal text-[clamp(1.25rem,2vw,1.75rem)] leading-none text-oxford/[0.10] tracking-[0.01em]">
                  Aethria
                </p>
                <p className="type-meta tracking-badge uppercase text-oxford/[0.18]">
                  Select a company to open the investment memo
                </p>
              </div>
              )}
            </aside>
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
