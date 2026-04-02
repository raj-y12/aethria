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

  return (
    <div className="h-screen flex flex-col overflow-hidden bg-paper">
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
                <div className="flex flex-col items-start gap-3 py-3">
                  {/* Mode toggles: Deals / Judgements / System — same mono scale as desktop spine */}
                  <div className="flex flex-col items-stretch gap-0.5 w-full">
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
                <div className="flex flex-col items-start gap-1 mt-3">
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
      <main className="flex-1 flex flex-col min-h-0 overflow-hidden px-4 pt-4 lg:pl-[11rem] lg:pr-6 lg:pt-6">
        <div className="flex-1 flex flex-col min-h-0 overflow-hidden">
        <div className="flex-1 flex flex-col lg:grid lg:grid-cols-[6fr_7fr] min-h-0 overflow-hidden pb-3 lg:pb-4 gap-4 lg:gap-4">
          <div className="flex min-w-0 min-h-0 flex-1 flex-col lg:min-h-0">
            {/* Title + pipeline summary — desktop only; escalations live here (not duplicated on SystemBar) */}
            <header className="flex-none mb-2 hidden lg:block min-w-0">
              <div>
                <h1 className="font-display font-normal text-[20px] leading-[1.4] text-oxford">
                  Aethria
                </h1>
                {data.settings?.fund_identity?.fund_name?.trim() && (
                  <p className="type-meta text-oxford/50 mt-1 tracking-[0.12em]" aria-hidden>
                    {[
                      data.settings.fund_identity.fund_name.trim(),
                      data.settings.fund_identity.stage_focus?.trim(),
                      data.settings.fund_identity.geographic_focus?.trim(),
                    ]
                      .filter(Boolean)
                      .join(' · ')}
                  </p>
                )}
              </div>
              <section
                aria-label="Pipeline summary and agent status"
                className="mt-2 flex min-w-0 flex-wrap items-baseline justify-between gap-x-3 gap-y-0.5 border border-hairline bg-paper px-2 py-1.5"
              >
                <p className="min-w-0 font-mono text-[10px] uppercase tracking-[0.1em] text-oxford/45">
                  Total <span className="text-oxford">{startups.length}</span>
                  <span className="mx-1.5 text-oxford/20">·</span>
                  Open <span className="text-oxford">{openCount}</span>
                  <span className="mx-1.5 text-oxford/20">·</span>
                  Esc <span className={pendingEscalations > 0 ? 'text-escalation' : 'text-oxford'}>{pendingEscalations}</span>
                  <span className="mx-1.5 text-oxford/20">·</span>
                  Dec <span className="text-oxford">{resolvedCount}</span>
                </p>
                <p className="shrink-0 text-right font-mono text-[10px] uppercase tracking-[0.1em] text-oxford/45">
                  Pipeline{' '}
                  <span className="relative inline-flex items-center gap-1">
                    <span className={pipelineStateLabel === 'Issue' ? 'text-escalation' : 'text-oxford'}>
                      {pipelineStateLabel}
                    </span>
                    {pipelineStateLabel === 'Issue' && (
                      <>
                        <button
                          type="button"
                          onClick={() => setShowPipelineIssueHelp((open) => !open)}
                          className="inline-flex h-3.5 w-3.5 items-center justify-center rounded-full border border-escalation/40 text-[9px] leading-none text-escalation hover:bg-escalation/10 btn-interaction focus:outline-none focus-visible:ring-2 focus-visible:ring-escalation/40"
                          aria-label="Why pipeline has an issue"
                          aria-expanded={showPipelineIssueHelp}
                        >
                          ?
                        </button>
                        {showPipelineIssueHelp && (
                          <span className="absolute right-0 top-[calc(100%+6px)] z-20 w-56 rounded-none border border-field-border bg-paper p-2 text-left normal-case tracking-normal text-[11px] leading-4 text-oxford shadow-none">
                            Pipeline has a problem and may not process updates right now.
                            <button
                              type="button"
                              onClick={() => navigate('/settings')}
                              className="mt-1.5 block text-[10px] uppercase tracking-[0.08em] text-oxford/70 hover:text-oxford btn-interaction"
                            >
                              Open settings
                            </button>
                          </span>
                        )}
                      </>
                    )}
                  </span>
                  <span className="mx-1.5 text-oxford/20">·</span>
                  Lookup <span className={lookupWorking ? 'text-escalation' : 'text-oxford'}>{lookupStateLabel}</span>
                </p>
              </section>
              <div className="mt-2 border border-hairline bg-paper">
                <button
                  type="button"
                  className="w-full flex items-center justify-between border-b border-hairline bg-paper px-2 py-1.5 type-meta uppercase tracking-[0.12em] text-oxford/50 hover:text-oxford/70 btn-interaction focus:outline-none focus-visible:ring-2 focus-visible:ring-oxford/40 focus-visible:ring-inset"
                  aria-expanded={lookupExpanded}
                  aria-controls="lookup-panel"
                  onClick={() => setLookupExpanded((open) => !open)}
                >
                  <span>On-demand lookup</span>
                  <span className="tabular-nums" aria-hidden>{lookupExpanded ? '−' : '+'}</span>
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
                      <div className="px-2 py-2">
                        <div className="flex items-center gap-2">
                          <input
                            type="text"
                            value={lookupInput}
                            onChange={(e) => setLookupInput(e.target.value)}
                            onKeyDown={(e) => {
                              if (e.key === 'Enter') void handleLookupSubmit();
                            }}
                            placeholder="Company name, website, or context"
                            className="h-8 flex-1 rounded-none border border-field-border bg-paper px-2 text-[12px] text-oxford outline-none focus:border-field-border-strong"
                          />
                          <button
                            type="button"
                            onClick={() => void handleLookupSubmit()}
                            disabled={lookupBusy || !lookupInput.trim()}
                            className="h-8 px-2 type-meta uppercase tracking-[0.08em] border border-field-border-strong text-oxford disabled:text-oxford/35 disabled:border-hairline-strong"
                          >
                            {lookupBusy ? 'Queueing...' : 'Queue'}
                          </button>
                        </div>
                        {lookupMessage ? (
                          <p className="mt-1 text-[11px] text-oxford/55">{lookupMessage}</p>
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
                className="flex-1 min-h-0 overflow-y-auto w-full min-w-0 rounded-none border border-hairline bg-paper"
                style={{ scrollbarGutter: 'stable both-edges' }}
              >
                <div className="px-0 pt-0 pb-6 lg:pb-8">
                  <GhostTransition disableLift>
                    <WorkGrid
                      startups={startups}
                      onStartupClick={handleStartupClick}
                      selectedId={selectedStartup?.id ?? null}
                      watchlistIds={watchlistIds}
                    />
                  </GhostTransition>
                </div>
              </div>
            )}
          </div>

          {/* Right zone: Judgements or memo only — never System. */}
          <aside
            className="hidden lg:flex flex-col min-w-0 min-h-0 border border-hairline bg-paper overflow-hidden"
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
                title=""
                showTitle={false}
                headerPaddingClass={SYSTEM_MEMO_HEADER_PADDING}
                headerBorderClass=""
                headerJustifyClass="justify-end"
                actions={
                  <div className="flex items-center gap-2">
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
                contentClassName="flex-1 min-h-0 overflow-y-auto px-5 py-5 sm:px-6 sm:py-6"
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
              <div className="flex-1 flex items-center justify-center p-8">
                <p className="type-label-tab text-oxford/25" style={{ transition: 'opacity var(--motion-micro) var(--motion-ease)' }}>
                  Click a deal to open the memo here
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
              backgroundColor: '#F2F0EA',
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
