import { useState, useRef, useCallback } from 'react';
import { createPortal } from 'react-dom';
import { motion, AnimatePresence } from 'framer-motion';
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
} from '../hooks';
import type { Startup } from '../types/startup';
import type { SystemData } from '../hooks/useSystemData';
import InvestmentMemoContent, { type InvestmentMemoContentHandle } from './InvestmentMemoContent';

interface MainLayoutProps {
  data: SystemData;
  startupsError?: string | null;
}

export default function MainLayout({ data, startupsError }: MainLayoutProps) {
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
  } = data;
  const [selectedStartup, setSelectedStartup] = useState<Startup | null>(null);
  const [rightPanel, setRightPanel] = useState<'memo' | 'feed' | 'system' | null>('system');

  const isDesktop = useMediaQuery('(min-width: 1024px)');
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const restoreRefVerdictMemo = useRef<HTMLElement | null>(null);
  const judgementsPanelRef = useRef<HTMLDivElement | null>(null);
  const memoContentRef = useRef<InvestmentMemoContentHandle | null>(null);

  const memoOpen = !!selectedStartup;
  const verdictOrMemoOpen = memoOpen;
  const judgementsAsOverlay = rightPanel === 'feed' && !isDesktop;
  const systemAsOverlay = rightPanel === 'system' && !isDesktop;
  const anyOverlayOpen = verdictOrMemoOpen || judgementsAsOverlay || systemAsOverlay;
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

  const handleEscape = useCallback(() => {
    if (memoOpen) handleCloseMemo();
    else if (rightPanel === 'feed') handleCloseJudgements();
    else if (rightPanel === 'system') setRightPanel(null);
  }, [memoOpen, rightPanel, handleCloseMemo, handleCloseJudgements]);

  useScrollLock(anyOverlayOpen);
  useEscapeKey(handleEscape, anyOverlayOpen);
  useRestoreFocus(verdictOrMemoOpen, restoreRefVerdictMemo, !(judgementsAsOverlay || systemAsOverlay));
  useRestoreFocus(judgementsAsOverlay || systemAsOverlay, { current: null }, !verdictOrMemoOpen);
  useFocusTrap(judgementsAsOverlay || systemAsOverlay, judgementsPanelRef);

  const resolvedCount = startups.filter((s) => s.partner?.decision != null).length;
  const queueDepths = data.settings?.system_health?.queue_depths;
  const unreviewed = queueDepths?.unreviewed ?? 0;
  const undecided = queueDepths?.undecided ?? 0;
  const watchlist = queueDepths?.watchlist ?? 0;
  const pendingEscalations = data.settings?.system_health?.pending_escalations ?? 0;

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
                transition={{ duration: tokens.motion.duration.micro, ease: tokens.motion.ease }}
                className="px-4 pb-0 border-b border-oxford/[0.06] type-label-tab bg-oxford overflow-hidden text-ivory/70"
                aria-label="Menu"
              >
                <div className="flex flex-col items-start gap-3 py-3">
                  {/* Mode toggles: Judgements / System */}
                  <div className="flex flex-col items-stretch gap-0.5 w-full">
                    <button
                      type="button"
                      onClick={() => {
                        setRightPanel((panel) => (panel === 'feed' ? null : 'feed'));
                        setMobileMenuOpen(false);
                      }}
                      className={`type-label-tab min-h-[44px] flex items-center justify-start cursor-pointer px-0 btn-interaction ${
                        rightPanel === 'feed' ? 'text-ivory' : 'text-ivory/60 hover:text-ivory'
                      }`}
                      style={{ transitionTimingFunction: 'var(--motion-ease)' }}
                      aria-pressed={rightPanel === 'feed'}
                    >
                      <span
                        className={`inline-block pb-0.5 ${rightPanel === 'feed' ? 'border-b-2 border-ivory' : ''}`}
                      >
                        Judgements
                      </span>
                    </button>
                    <button
                      type="button"
                      onClick={() => {
                        setRightPanel((panel) => (panel === 'system' ? null : 'system'));
                        setMobileMenuOpen(false);
                      }}
                      className={`type-label-tab min-h-[44px] flex items-center justify-start cursor-pointer px-0 btn-interaction ${
                        rightPanel === 'system' ? 'text-ivory' : 'text-ivory/60 hover:text-ivory'
                      }`}
                      style={{ transitionTimingFunction: 'var(--motion-ease)' }}
                      aria-pressed={rightPanel === 'system'}
                    >
                      <span
                        className={`inline-block pb-0.5 ${rightPanel === 'system' ? 'border-b-2 border-ivory' : ''}`}
                      >
                        System
                      </span>
                    </button>
                  </div>

                {/* Settings */}
                <div className="flex flex-col items-start gap-1 mt-3">
                  <a
                    href="/settings"
                    className="type-label-section text-ivory/70 hover:text-ivory btn-interaction"
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
        scoutCount={startups.length}
        rightPanel={rightPanel}
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
      <main className="flex-1 flex flex-col min-h-0 overflow-hidden px-4 pt-4 lg:pl-[13rem] lg:pr-6 lg:pt-6">
        <div className="flex-1 flex flex-col min-h-0 overflow-hidden">
        <div className="flex-1 flex flex-col lg:grid lg:grid-cols-[3fr_2fr] min-h-0 overflow-hidden pb-3 lg:pb-4 gap-4 lg:gap-4">
          <div className="flex flex-col min-w-0 min-h-0">
            {/* Title above status strip — desktop only; mobile uses top nav title */}
            <header className="flex-none mb-2 hidden lg:block">
              <h1 className="type-hero font-bold text-oxford">
                Aethria
              </h1>
              {data.settings?.fund_identity?.fund_name?.trim() && (
                <p className="type-meta text-oxford/50 mt-1" aria-hidden>
                  {[
                    data.settings.fund_identity.fund_name.trim(),
                    data.settings.fund_identity.stage_focus?.trim(),
                    data.settings.fund_identity.geographic_focus?.trim(),
                  ]
                    .filter(Boolean)
                    .join(' · ')}
                </p>
              )}
            </header>

            {/* Status strip: single-line summary — desktop only; mobile shows this in the menu */}
            <section className="hidden lg:flex flex-none h-11 mb-2 items-center py-[6px]">
              <div className="w-full flex items-center type-meta">
                {/* Pipeline counts (left) — friendly line when nothing yet */}
                <span className="text-oxford/60 type-label-section">
                  {startups.length === 0 && resolvedCount === 0 && pendingEscalations === 0
                    ? 'Autonomous dealflow'
                    : `${startups.length} companies · ${resolvedCount} decided`}
                </span>

                {/* Separator */}
                <span
                  className="mx-[12px]"
                    style={{
                      width: '3px',
                      height: '3px',
                      borderRadius: '9999px',
                      backgroundColor: 'rgba(0,33,71,0.25)',
                    }}
                  aria-hidden
                />

                {/* Queue depths (middle) */}
                <span className="text-oxford/60">
                  Unreviewed {unreviewed} · Undecided {undecided} · Watchlist {watchlist}
                </span>

                {/* Separator */}
                <span
                  className="mx-[12px]"
                    style={{
                      width: '3px',
                      height: '3px',
                      borderRadius: '9999px',
                      backgroundColor: 'rgba(0,33,71,0.25)',
                    }}
                  aria-hidden
                />

                {/* Escalations (right) */}
                <span className="flex items-center gap-2">
                  <span
                    className={pendingEscalations > 0 ? 'escalation-dot-active' : ''}
                    style={{
                      width: '6px',
                      height: '6px',
                      borderRadius: '50%',
                      backgroundColor:
                        pendingEscalations > 0 ? 'var(--color-accent)' : 'rgba(0,33,71,0.25)', /* accent: escalation-only */
                    }}
                    aria-hidden
                  />
                  <span
                    style={{
                      color:
                          pendingEscalations > 0
                          ? 'rgba(125, 43, 58, 0.85)' /* escalation count: accent tint */
                          : 'rgba(0, 33, 71, 0.4)',
                    }}
                  >
                    {pendingEscalations} escalations
                  </span>
                </span>
              </div>
            </section>

            {/* WorkGrid: only this area scrolls; fills column so both columns resize together */}
            <div className="flex-1 min-h-0 overflow-y-auto w-full min-w-0 rounded-none border border-oxford/[0.06] bg-paper">
              <div className="px-4 sm:px-6 lg:px-10 pt-2 pb-6 lg:pb-8">
                <GhostTransition>
                  <WorkGrid
                    startups={startups}
                    onStartupClick={handleStartupClick}
                    selectedId={selectedStartup?.id ?? null}
                  />
                </GhostTransition>
              </div>
            </div>
          </div>

          {/* Right panel on desktop: Judgements, System Intelligence, Memo, or empty. */}
          <aside
            className="hidden lg:flex flex-col min-w-0 min-h-0 border border-oxford/[0.06] bg-paper overflow-hidden"
            aria-live="polite"
            aria-label={
              rightPanel === 'system'
                ? 'System intelligence'
                : rightPanel === 'feed'
                ? 'Judgements'
                : selectedStartup
                ? 'Investment memo'
                : 'Detail'
            }
          >
            {rightPanel === 'system' ? (
              <PanelShell
                title="System"
                actions={
                  <button
                    type="button"
                    onClick={() => setRightPanel(null)}
                    className="type-label-tab text-oxford/60 hover:text-oxford btn-interaction focus:outline-none focus-visible:ring-2 focus-visible:ring-oxford/40 focus-visible:ring-inset"
                    aria-label="Hide system intelligence"
                  >
                    Close
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
                />
              </PanelShell>
            ) : rightPanel === 'feed' ? (
              <PanelShell
                title="Judgements"
                actions={
                  <button
                    type="button"
                    onClick={handleCloseJudgements}
                    className="type-label-tab text-oxford/60 hover:text-oxford btn-interaction focus:outline-none focus-visible:ring-2 focus-visible:ring-oxford/40 focus-visible:ring-inset"
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
            ) : selectedStartup ? (
              <PanelShell
                title="Memo"
                actions={
                  <div className="flex items-center gap-2">
                    <button
                      type="button"
                      onClick={() => memoContentRef.current?.downloadPDF()}
                      className="type-label-tab text-oxford/60 hover:text-oxford btn-interaction focus:outline-none focus-visible:ring-2 focus-visible:ring-oxford/40 focus-visible:ring-inset"
                    >
                      Download PDF
                    </button>
                    <button
                      type="button"
                      onClick={handleCloseMemo}
                      className="type-label-tab text-oxford/60 hover:text-oxford btn-interaction focus:outline-none focus-visible:ring-2 focus-visible:ring-oxford/40 focus-visible:ring-inset"
                      aria-label="Close memo"
                    >
                      Close
                    </button>
                  </div>
                }
                contentClassName="flex-1 min-h-0 overflow-y-auto px-6 sm:px-8 py-6"
              >
                <InvestmentMemoContent ref={memoContentRef} startup={selectedStartup} embedded />
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

      {/* Judgements/System as slide-over only on mobile; on desktop they appear in the right panel. */}
      {(judgementsAsOverlay || systemAsOverlay) && typeof document !== 'undefined' && createPortal(
        <AnimatePresence>
          <motion.div
            key="judgements-overlay"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: tokens.motion.duration.medium, ease: tokens.motion.ease }}
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
            onClick={judgementsAsOverlay ? handleCloseJudgements : () => setRightPanel(null)}
            aria-hidden="true"
          />
          <motion.div
            ref={judgementsPanelRef}
            key="judgements-panel"
            initial={{ x: '100%' }}
            animate={{ x: 0 }}
            exit={{ x: '100%' }}
            transition={{ duration: tokens.motion.duration.medium, ease: tokens.motion.ease }}
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
              title={judgementsAsOverlay ? 'Judgements' : 'System'}
              actions={
                <button
                  type="button"
                  onClick={judgementsAsOverlay ? handleCloseJudgements : () => setRightPanel(null)}
                  className="type-label-tab text-oxford/60 hover:text-oxford btn-interaction focus:outline-none focus-visible:ring-2 focus-visible:ring-oxford/40 focus-visible:ring-inset min-w-[44px] min-h-[44px] flex items-center justify-center"
                  aria-label={judgementsAsOverlay ? 'Close judgements panel' : 'Close system panel'}
                >
                  Close
                </button>
              }
              contentOverflowHidden
              contentClassName="flex-1 min-h-0 overflow-hidden"
              className="h-full"
            >
              {judgementsAsOverlay ? (
                <LiveIntelligenceFeed
                  startups={startups}
                  signals={signals}
                  metaReports={metaReports}
                />
              ) : (
                <SystemIntelligence
                  signals={signals}
                  escalations={escalations}
                  rejectionAnalytics={rejectionAnalytics}
                  watchlistAnalytics={watchlistAnalytics}
                  concentrationAnalytics={concentrationAnalytics}
                  metaReports={metaReports}
                  scoutWeights={scoutWeights}
                  calibrationState={calibrationState}
                />
              )}
            </PanelShell>
          </motion.div>
        </AnimatePresence>,
        document.body
      )}

      {/* Memo modal on small viewports; on desktop the right panel shows the memo. */}
      <AnimatePresence initial={false}>
        {useModal && selectedStartup && (
          <InvestmentMemo
            key="memo"
            startup={selectedStartup}
            onClose={handleCloseMemo}
          />
        )}
      </AnimatePresence>
    </div>
  );
}
