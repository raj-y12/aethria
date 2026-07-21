import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useLayoutEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from 'react';
import { useNavigate, useLocation } from 'react-router';
import { useQuery } from '@tanstack/react-query';
import { motion, AnimatePresence, LayoutGroup } from 'framer-motion';
import { LookupResultSnapshot } from '@aethria/product-chrome';
import AppSpine, {
  SPINE_WORKSPACES,
  isSpineRouteActive,
  type SpineMandate,
  type SpineOverride,
  type SpineTelemetry,
} from './AppSpine';
import MobileHeader from './MobileHeader';
import AgentLogoutModal from './AgentLogoutModal';
import DispatchCommandBar from './DispatchCommandBar';
import LookupReadyToast from './LookupReadyToast';
import IdentityReviewCenter from './identity/IdentityReviewCenter';
import { useAgentLogoutFlow } from '../hooks/useAgentLogoutFlow';
import { tokens } from '../design-system/tokens';
import { transitionOrReduced } from '../design-system/motion';
import {
  useMediaQuery,
  usePrefersReducedMotion,
  useScrollLock,
  useFundConfiguration,
} from '../hooks';
import { useDispatchLookup, type LookupPhaseLabel } from '../hooks/useDispatchLookup';
import { useAcknowledgeStartup } from '../hooks/useAcknowledgeStartup';
import { fetchAgentsStatus, fetchLoopStatus } from '../api/agents';
import { fetchFundThesisSummary } from '../api/fundThesis';
import { getQueryConfig } from '../lib/queryIntent';
import { buildMandateSummaryLine } from '../lib/railSummaries';
import { isDealHumanResolved, isDealUnresolved } from '../lib/dealState';
import type { SystemData } from '../hooks/useSystemData';
import type { Startup } from '../types/startup';
import { deriveExecutionReadiness } from './institutional/ExecutionReadinessPanel';
import { operatorTypedContext } from './memo/memoContentHelpers';

export interface InlineDispatchProps {
  input: string;
  setInput: (v: string) => void;
  onSubmit: () => void;
  onCancel: () => void;
  isBusy: boolean;
  message: string | null;
  onClearMessage: () => void;
  lookupPhase: LookupPhaseLabel;
}

interface AppFrameContextValue {
  openDispatch: () => void;
  /** Open the takeover on an existing memo's company to add context and re-run the review. */
  openRerun: (startup: Startup) => void;
  dispatchActive: boolean;
  inlineDispatch: InlineDispatchProps;
  /** Pages report full-screen overlays (e.g. the mobile memo) so body scroll locking stays single-owner. */
  setPageOverlayOpen: (open: boolean) => void;
  /** A room can take over the spine's contextual regions (see SpineOverride). */
  setSpineOverride: (override: SpineOverride | null) => void;
  /** False only while bare chrome is becoming a full workspace frame. */
  workspaceChromeReady: boolean;
}

const AppFrameContext = createContext<AppFrameContextValue | null>(null);

export function useAppFrame(): AppFrameContextValue {
  const ctx = useContext(AppFrameContext);
  if (!ctx) throw new Error('useAppFrame must be used within AppFrame');
  return ctx;
}

interface AppFrameProps {
  data: SystemData;
  startupsError?: string | null;
  /**
   * 'bare' drops the spine and mobile chrome — the front door (Today) is a
   * centered Dispatch-style surface that carries its own navigation keys.
   */
  chrome?: 'full' | 'bare';
  children: ReactNode;
}

/**
 * The application frame: spine (oxford rail) + workspace area + the global
 * Dispatch command surface. Every workspace renders inside this frame so the
 * instrument's identity, telemetry, and ⌘K research are constant.
 */
export default function AppFrame({ data, startupsError, chrome = 'full', children }: AppFrameProps) {
  const navigate = useNavigate();
  const { pathname } = useLocation();
  const bareChrome = chrome === 'bare';
  const isDesktop = useMediaQuery('(min-width: 1024px)');
  const reduceMotion = usePrefersReducedMotion();
  const previousChrome = useRef(chrome);
  const [workspaceChromeReady, setWorkspaceChromeReady] = useState(true);
  const enteringFullChrome = previousChrome.current === 'bare' && chrome === 'full';
  const resolvedWorkspaceChromeReady =
    reduceMotion || (!enteringFullChrome && workspaceChromeReady);
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [pageOverlayOpen, setPageOverlayOpen] = useState(false);
  const [spineOverride, setSpineOverride] = useState<SpineOverride | null>(null);
  // Mobile log out — desktop logs out from the spine's operator block.
  const {
    requestLogout: requestMobileLogout,
    agentActionPending: mobileLogoutPending,
    logoutModalProps: mobileLogoutModalProps,
  } = useAgentLogoutFlow();
  const { configuration: fundConfiguration } = useFundConfiguration(data.settings);
  const { startups, liveGate } = data;

  useLayoutEffect(() => {
    const previous = previousChrome.current;
    previousChrome.current = chrome;

    if (reduceMotion || chrome === 'bare') {
      setWorkspaceChromeReady(true);
      return;
    }

    if (previous === 'bare') setWorkspaceChromeReady(false);
  }, [chrome, reduceMotion]);

  const completeWorkspaceChromeEntrance = useCallback(() => {
    setWorkspaceChromeReady(true);
  }, []);

  const acknowledge = useAcknowledgeStartup();
  const handleOpenMemo = useCallback(
    (startup: Startup) => {
      if (startup.is_new_to_user) acknowledge(startup);
      navigate(`/v1/flow?open=${startup.id}`);
    },
    [acknowledge, navigate],
  );

  const dispatch = useDispatchLookup({
    startups,
    liveGate,
    fundConfiguration,
    onOpenMemo: handleOpenMemo,
  });

  // Scroll lock has one owner: the frame. Covers the dispatch takeover and any
  // full-screen page overlay (mobile memo) without double-locking the body.
  useScrollLock(dispatch.commandBarOpen || pageOverlayOpen);

  // Places have names — the browser tab is part of the instrument.
  useEffect(() => {
    const place = pathname.startsWith('/v1/settings')
      ? 'Settings'
      : SPINE_WORKSPACES.find((w) => isSpineRouteActive(w.href, pathname))?.label;
    document.title = place ? `${place} — Aethria` : 'Aethria';
    return () => {
      document.title = 'Aethria';
    };
  }, [pathname]);

  // ⌘K opens Dispatch; 1/2/3 move between workspaces — from anywhere.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && (e.key === 'k' || e.key === 'K')) {
        e.preventDefault();
        dispatch.openCommandBar();
        return;
      }
      if (e.defaultPrevented || e.metaKey || e.ctrlKey || e.altKey) return;
      const target = e.target as HTMLElement | null;
      const tagName = target?.tagName?.toLowerCase();
      if (target?.isContentEditable || tagName === 'input' || tagName === 'textarea' || tagName === 'select') return;
      const workspace = SPINE_WORKSPACES.find((w) => w.shortcut === e.key);
      if (workspace) {
        e.preventDefault();
        navigate(workspace.href);
      }
    };
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, [dispatch.openCommandBar, navigate]);

  // ── Telemetry (spine readout) ──────────────────────────────────────────────
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

  const agentConfig = data.settings?.agent_config;
  const pipelineEnabled =
    !!agentConfig && !!(agentConfig.scouts_enabled || agentConfig.reviewers_enabled || agentConfig.partners_enabled);
  const executionReadiness = deriveExecutionReadiness(data.systemStatus);
  const agentRuntimeIssue = agentsStatus != null && (
      !agentsStatus.worker_ready ||
      !agentsStatus.supabase_configured ||
      !agentsStatus.openai_configured ||
      !agentsStatus.agents_will_run ||
      agentsStatus.execution_prerequisites_ready === false
    );
  const pipelineHealthIssue =
    pipelineEnabled &&
    (
      agentRuntimeIssue ||
      executionReadiness === 'blocked' ||
      executionReadiness === 'degraded'
    );
  const pipelineStopping = Boolean(loopStatus?.loop_alive && loopStatus?.agents_enabled === false && !pipelineHealthIssue);
  const pipelineLoopAlive = Boolean(loopStatus?.loop_alive && agentsStatus?.agents_will_run === true && !pipelineHealthIssue);
  const pipelineState = pipelineStopping
    ? 'Stopping'
    : !pipelineEnabled
      ? 'Off'
      : pipelineHealthIssue
        ? 'Issue'
        : pipelineLoopAlive
          ? 'Live'
          : 'Idle';

  const telemetry: SpineTelemetry = {
    pendingEscalations: data.pendingEscalationCount ?? data.settings?.system_health?.pending_escalations ?? 0,
    openInProgressCount: startups.filter(isDealUnresolved).length,
    totalCount: startups.length,
    agentDecidedCount: startups.filter((s) => Boolean(s.partner?.recommendation) && !isDealHumanResolved(s)).length,
    humanRuledCount: startups.filter(isDealHumanResolved).length,
    newCount: startups.filter((s) => s.is_new_to_user).length,
    pipelineState,
    executionReadiness,
  };

  // ── Mandate (spine block) ─────────────────────────────────────────────────
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

  const mandateSummaryLine = useMemo(() => {
    const pj = fundThesisSummary?.parsed_json as Record<string, unknown> | undefined;
    const toStrings = (v: unknown): string[] => {
      if (Array.isArray(v)) return v.filter((x): x is string => typeof x === 'string' && !!x.trim()).map((x) => x.trim());
      if (typeof v === 'string' && v.trim()) return [v.trim()];
      return [];
    };
    const fundStage = data.settings?.fund_identity?.stage_focus?.trim() || '';
    const fundGeo = data.settings?.fund_identity?.geographic_focus?.trim() || '';
    const sectors = pj ? toStrings(pj.sectors ?? pj.sector ?? pj.focus_areas) : [];
    const stages = pj ? toStrings(pj.stage_focus ?? pj.stage) : toStrings(fundStage);
    const geos = pj ? toStrings(pj.geography ?? pj.geographies ?? pj.geographic_focus) : [];
    return buildMandateSummaryLine({
      stages: stages.length ? stages : fundStage ? [fundStage] : [],
      geos: geos.length ? geos : fundGeo ? [fundGeo] : [],
      sectors,
    });
  }, [fundThesisSummary, data.settings?.fund_identity]);

  const mandate: SpineMandate = {
    hasThesis,
    fundName,
    summaryLine: mandateSummaryLine,
    versionNumber: fundThesisSummary?.active_version_number ?? null,
  };

  const inlineDispatch: InlineDispatchProps = {
    input: dispatch.input,
    setInput: dispatch.setInput,
    onSubmit: () => void dispatch.submit(),
    onCancel: dispatch.cancel,
    isBusy: dispatch.lookupWorking,
    message: dispatch.message,
    onClearMessage: dispatch.clearMessage,
    lookupPhase: dispatch.phaseLabel,
  };

  const contextValue: AppFrameContextValue = {
    openDispatch: dispatch.openCommandBar,
    openRerun: dispatch.openRerun,
    dispatchActive: dispatch.lookupWorking,
    inlineDispatch,
    setPageOverlayOpen,
    setSpineOverride,
    workspaceChromeReady: resolvedWorkspaceChromeReady,
  };

  const chromeTransition = transitionOrReduced(reduceMotion, {
    duration: tokens.motion.duration.long,
    ease: tokens.motion.ease,
    layout: { duration: tokens.motion.duration.long, ease: tokens.motion.ease },
  });

  /** Dispatch is a front-door surface — hide workspace chrome while it is open. */
  const showSpine = !bareChrome && !dispatch.commandBarOpen;
  const showMobileChrome = !isDesktop && !bareChrome && !dispatch.commandBarOpen;

  return (
    <AppFrameContext.Provider value={contextValue}>
      <div className="flex h-[100dvh] flex-col overflow-hidden bg-paper">
        <IdentityReviewCenter />
        <LookupReadyToast
          name={dispatch.lookupReady?.scout?.name ?? null}
          recommendation={dispatch.lookupReady?.partner?.recommendation ?? null}
          onOpen={dispatch.openLookupMemo}
          onDismiss={dispatch.dismissReady}
        />

        {/* Mobile / tablet top nav — desktop carries identity in the spine */}
        <AnimatePresence initial={false}>
          {showMobileChrome ? (
            <motion.div
              key="mobile-chrome"
              initial={reduceMotion ? { opacity: 1 } : { opacity: 0, y: -10 }}
              animate={{ opacity: 1, y: 0 }}
              exit={reduceMotion ? { opacity: 0 } : { opacity: 0, y: -10 }}
              transition={chromeTransition}
              onAnimationComplete={completeWorkspaceChromeEntrance}
              className="flex-none"
            >
              <MobileHeader onMenuToggle={() => setMobileMenuOpen((open) => !open)} />
              <AnimatePresence>
                {mobileMenuOpen && (
                  <motion.nav
                    id="mobile-menu"
                    initial={{ opacity: 0, y: -8 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0, y: -8 }}
                    transition={transitionOrReduced(reduceMotion, {
                      duration: tokens.motion.duration.micro,
                      ease: tokens.motion.ease,
                    })}
                    className="border-b border-white/[0.08] bg-oxford px-phi-4 py-phi-3"
                    aria-label="Workspaces"
                  >
                    <div className="flex flex-col items-stretch gap-phi-1">
                      {SPINE_WORKSPACES.map((item) => (
                        <button
                          key={item.href}
                          type="button"
                          onClick={() => {
                            navigate(item.href);
                            setMobileMenuOpen(false);
                          }}
                          className="type-label-tab flex min-h-[44px] items-center px-1 text-white/60 hover:text-white btn-interaction"
                        >
                          {item.label}
                        </button>
                      ))}
                      <button
                        type="button"
                        onClick={() => {
                          navigate('/v1/settings');
                          setMobileMenuOpen(false);
                        }}
                        className="type-label-tab flex min-h-[44px] items-center px-1 text-white/60 hover:text-white btn-interaction"
                      >
                        Settings
                      </button>
                      <button
                        type="button"
                        onClick={() => {
                          setMobileMenuOpen(false);
                          requestMobileLogout();
                        }}
                        disabled={mobileLogoutPending}
                        className="type-label-tab flex min-h-[44px] items-center border-t border-white/[0.07] px-1 text-white/60 hover:text-white disabled:opacity-50 btn-interaction"
                      >
                        {mobileLogoutPending ? 'Updating...' : 'Log out'}
                      </button>
                    </div>
                  </motion.nav>
                )}
              </AnimatePresence>
              <AgentLogoutModal {...mobileLogoutModalProps} />
            </motion.div>
          ) : null}
        </AnimatePresence>

        {startupsError && (
          <div
            role="status"
            title={startupsError}
            className="flex flex-none items-center justify-between gap-phi-4 border-b border-oxford/25 bg-warning px-6 py-2 type-label-tab text-oxford"
          >
            <span>Can't reach the Aethria service — the deal flow shown may be out of date.</span>
            <button
              type="button"
              onClick={() => window.location.reload()}
              className="shrink-0 border-b border-oxford/60 uppercase text-oxford hover:border-oxford btn-interaction"
            >
              Retry
            </button>
          </div>
        )}

        <LayoutGroup id="app-frame">
          <div className="flex min-h-0 flex-1 overflow-hidden">
            <AnimatePresence initial={false} mode="popLayout">
              {showSpine ? (
                <motion.div
                  key="spine"
                  layout
                  initial={reduceMotion ? { opacity: 1 } : { opacity: 0, x: -28 }}
                  animate={{ opacity: 1, x: 0 }}
                  exit={reduceMotion ? { opacity: 0 } : { opacity: 0, x: -28 }}
                  transition={chromeTransition}
                  onAnimationComplete={completeWorkspaceChromeEntrance}
                  className="hidden lg:flex flex-none overflow-hidden"
                >
                  <AppSpine
                    telemetry={telemetry}
                    mandate={mandate}
                    dispatchActive={dispatch.lookupWorking}
                    onDispatch={dispatch.openCommandBar}
                    override={spineOverride}
                  />
                </motion.div>
              ) : null}
            </AnimatePresence>
            <motion.main
              layout="position"
              transition={chromeTransition}
              className="relative flex min-h-0 min-w-0 flex-1 flex-col overflow-hidden bg-paper"
            >
              {children}
              <AnimatePresence initial={false}>
                {dispatch.commandBarOpen ? (
                  <motion.div
                    key="dispatch-takeover"
                    initial={reduceMotion ? { opacity: 1 } : { opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={reduceMotion ? { opacity: 0 } : { opacity: 0, y: 10 }}
                    transition={transitionOrReduced(reduceMotion, {
                      duration: tokens.motion.duration.short,
                      ease: tokens.motion.ease,
                    })}
                    className="absolute inset-0 z-20"
                  >
                    <DispatchCommandBar
                      open
                      onClose={dispatch.closeCommandBar}
                      input={dispatch.input}
                      setInput={dispatch.setInput}
                      onSubmit={() => void dispatch.submit()}
                      onCancel={dispatch.cancel}
                      isBusy={dispatch.busy}
                      message={dispatch.message}
                      onClearMessage={dispatch.clearMessage}
                      lookupPhase={dispatch.phaseLabel}
                      progress={dispatch.progress}
                      execution={dispatch.execution}
                      onRetryJob={() => void dispatch.retryDurableJob()}
                      onOpenIdentityReview={dispatch.openIdentityReview}
                      chips={dispatch.chips}
                      onFocusChip={dispatch.focusChip}
                      failure={dispatch.failure}
                      onRetry={dispatch.dismissFailure}
                      candidates={dispatch.candidates}
                      needsWebsite={dispatch.needsWebsite}
                      onPickCandidate={dispatch.pickCandidate}
                      onRefineWebsite={dispatch.refineWithWebsite}
                      rerun={
                        dispatch.rerunTarget
                          ? {
                              name: dispatch.rerunTarget.scout.name,
                              sector: dispatch.rerunTarget.scout.sector ?? null,
                              previousContext: operatorTypedContext(dispatch.rerunTarget) || null,
                            }
                          : null
                      }
                      onSubmitRerun={(context) => void dispatch.submitRerun(context)}
                      result={
                        dispatch.lookupDecided && dispatch.snapshotProps ? (
                          <LookupResultSnapshot
                            {...dispatch.snapshotProps}
                            onOpenMemo={dispatch.openLookupMemo}
                            className="w-full"
                          />
                        ) : null
                      }
                    />
                  </motion.div>
                ) : null}
              </AnimatePresence>
            </motion.main>
          </div>
        </LayoutGroup>
      </div>
    </AppFrameContext.Provider>
  );
}
