import { useState, useRef, useCallback } from 'react';
import { createPortal } from 'react-dom';
import { motion, AnimatePresence } from 'framer-motion';
import { tokens } from '../design-system/tokens';
import SystemBar from './SystemBar';
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

  const displayName = typeof sessionStorage !== 'undefined' ? sessionStorage.getItem('authUser') : null;
  const handleLogout = () => {
    try {
      localStorage.removeItem('aethria_last_activity');
      sessionStorage.removeItem('auth');
      sessionStorage.removeItem('authUser');
    } finally {
      window.location.reload();
    }
  };

  return (
    <div className="h-screen flex flex-col overflow-hidden bg-paper">
      {/* Mobile / tablet top nav — desktop keeps the vertical SystemBar only */}
      {!isDesktop && (
        <>
          <header className="flex items-center justify-between px-4 pt-[max(1.25rem,env(safe-area-inset-top))] pb-3 border-b border-oxford/[0.06] bg-oxford">
            <span
              className="text-[18px] tracking-tight"
              style={{ fontFamily: tokens.font.display, letterSpacing: '-0.02em', color: '#F2F0EA' }}
            >
              Aethria
            </span>
            <button
              type="button"
              onClick={() => setMobileMenuOpen((open) => !open)}
              className="font-mono text-[10px] uppercase tracking-[0.18em] text-ivory/70"
            >
              Menu
            </button>
          </header>
          {mobileMenuOpen && (
            <section
              className="px-4 pb-3 border-b border-oxford/[0.06] font-mono text-[10px] uppercase bg-oxford"
              style={{ letterSpacing: '0.12em', color: 'rgba(242,240,234,0.7)' }}
            >
              <div className="flex flex-col items-start gap-3 py-3">
                {/* Mode toggles: Judgements / System */}
                <div className="flex flex-col items-start gap-1">
                  <button
                    type="button"
                    onClick={() => {
                      setRightPanel((panel) => (panel === 'feed' ? null : 'feed'));
                      setMobileMenuOpen(false);
                    }}
                    className="transition-transform duration-200 hover:-translate-y-[1px] hover:opacity-80"
                    style={{
                      fontFamily: tokens.font.mono,
                      fontSize: '10px',
                      textTransform: 'uppercase',
                      letterSpacing: '0.1em',
                      color: rightPanel === 'feed' ? 'rgba(242,240,234,1)' : 'rgba(242,240,234,0.5)',
                      background: 'none',
                      border: 'none',
                      borderBottom: rightPanel === 'feed' ? '1px solid rgba(242,240,234,1)' : '1px solid transparent',
                      paddingBottom: rightPanel === 'feed' ? '3px' : 0,
                      cursor: 'pointer',
                    }}
                  >
                    Judgements
                  </button>
                  <button
                    type="button"
                    onClick={() => {
                      setRightPanel((panel) => (panel === 'system' ? null : 'system'));
                      setMobileMenuOpen(false);
                    }}
                    className="transition-transform duration-200 hover:-translate-y-[1px] hover:opacity-80"
                    style={{
                      fontFamily: tokens.font.mono,
                      fontSize: '10px',
                      textTransform: 'uppercase',
                      letterSpacing: '0.1em',
                      color: rightPanel === 'system' ? 'rgba(242,240,234,1)' : 'rgba(242,240,234,0.5)',
                      background: 'none',
                      border: 'none',
                      borderBottom: rightPanel === 'system' ? '1px solid rgba(242,240,234,1)' : '1px solid transparent',
                      paddingBottom: rightPanel === 'system' ? '3px' : 0,
                      cursor: 'pointer',
                    }}
                  >
                    System
                  </button>
                </div>

                {/* Settings / username / logout */}
                <div className="flex flex-col items-start gap-1 mt-3">
                  <a
                    href="/settings"
                    className="font-mono text-[10px] uppercase tracking-[0.16em] text-ivory/70 hover:text-ivory transition-colors"
                  >
                    Settings
                  </a>
                  {displayName && (
                    <span
                      style={{
                        fontFamily: tokens.font.body,
                        fontSize: '11px',
                        fontWeight: 400,
                        color: 'rgba(242, 240, 234, 0.6)',
                      }}
                    >
                      {displayName}
                    </span>
                  )}
                  <button
                    type="button"
                    onClick={handleLogout}
                    className="font-mono text-[10px] uppercase tracking-[0.16em] text-ivory/50 hover:text-ivory/80 transition-colors"
                  >
                    Log out
                  </button>
                </div>
              </div>
            </section>
          )}
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
        <div className="flex-none px-6 py-2 bg-amber-100 text-amber-900 font-mono text-[10px] uppercase tracking-wider">
          {startupsError} — Check API URL (VITE_API_URL) and backend CORS (ALLOWED_ORIGINS).
        </div>
      )}

      {/* Paper canvas. Fixed height so only WorkGrid scrolls.
          On desktop content is offset to clear vertical SystemBar; on mobile it uses standard page padding. */}
      <main className="flex-1 flex flex-col min-h-0 overflow-hidden px-4 pt-4 lg:pl-[13rem] lg:pr-6 lg:pt-6">
        <div className="flex-1 flex flex-col lg:grid lg:grid-cols-[3fr_2fr] min-h-0 overflow-hidden pb-3 lg:pb-4 gap-4 lg:gap-4">
          <div className="flex flex-col min-w-0 min-h-0">
            {/* Title above status strip — desktop only; mobile uses top nav title */}
            <header className="flex-none mb-4 hidden lg:block">
              <h1
                className="text-2xl text-oxford tracking-tight"
                style={{ fontFamily: tokens.font.display, letterSpacing: '-0.02em' }}
              >
                Aethria
              </h1>
            </header>

            {/* Status strip: single-line summary — desktop only; mobile shows this in the menu */}
            <section className="hidden lg:flex flex-none h-11 mb-4 border-b border-[rgba(0,33,71,0.07)] items-center py-[6px]">
              <div className="w-full flex items-center text-[10px] font-mono uppercase" style={{ letterSpacing: '0.08em' }}>
                {/* Pipeline counts (left) */}
                <span className="text-oxford/55 text-[11px]">
                  {startups.length} companies · {resolvedCount} decided
                </span>

                {/* Separator */}
                <span
                  className="mx-[12px]"
                  style={{
                    width: '3px',
                    height: '3px',
                    borderRadius: '9999px',
                    backgroundColor: 'rgba(0,33,71,0.30)',
                  }}
                  aria-hidden
                />

                {/* Queue depths (middle) */}
                <span className="text-oxford/35">
                  Unreviewed {unreviewed} · Undecided {undecided} · Watchlist {watchlist}
                </span>

                {/* Separator */}
                <span
                  className="mx-[12px]"
                  style={{
                    width: '3px',
                    height: '3px',
                    borderRadius: '9999px',
                    backgroundColor: 'rgba(0,33,71,0.30)',
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
                        pendingEscalations > 0 ? 'var(--color-accent)' : 'rgba(0,33,71,0.25)',
                    }}
                    aria-hidden
                  />
                  <span
                    style={{
                      color:
                        pendingEscalations > 0
                          ? 'rgba(125, 43, 58, 0.85)'
                          : 'rgba(0, 33, 71, 0.3)',
                    }}
                  >
                    {pendingEscalations} escalations awaiting review
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
              <>
                <div className="flex-none flex items-center justify-between px-6 py-4 border-b border-oxford/[0.06]">
                  <span className="font-mono text-[10px] uppercase tracking-[0.22em] text-oxford/50">
                    System
                  </span>
                  <button
                    type="button"
                    onClick={() => setRightPanel(null)}
                    className="font-mono text-[10px] uppercase tracking-[0.22em] text-oxford/50 hover:text-oxford transition-colors"
                    aria-label="Hide system intelligence"
                  >
                    Close
                  </button>
                </div>
                <div className="flex-1 min-h-0 overflow-hidden">
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
                </div>
              </>
            ) : rightPanel === 'feed' ? (
              <>
                <div className="flex-none flex items-center justify-between px-6 py-4 border-b border-oxford/[0.06]">
                  <span className="font-mono text-[10px] uppercase tracking-[0.22em] text-oxford/50">
                    Judgements
                  </span>
                  <button
                    type="button"
                    onClick={handleCloseJudgements}
                    className="font-mono text-[10px] uppercase tracking-[0.22em] text-oxford/50 hover:text-oxford transition-colors"
                    aria-label="Hide judgements"
                  >
                    Close
                  </button>
                </div>
                <div className="flex-1 min-h-0 overflow-hidden">
                  <LiveIntelligenceFeed startups={startups} />
                </div>
              </>
            ) : selectedStartup ? (
              <>
                <div className="flex-none flex items-center justify-between px-6 py-4 border-b border-oxford/[0.06]">
                  <span className="font-mono text-[10px] uppercase tracking-[0.22em] text-oxford/50">
                    Memo
                  </span>
                  <div className="flex items-center gap-2">
                    <button
                      type="button"
                      onClick={() => memoContentRef.current?.downloadPDF()}
                      className="font-mono text-[10px] uppercase tracking-[0.22em] text-oxford/50 hover:text-oxford transition-colors"
                    >
                      Download PDF
                    </button>
                    <button
                      type="button"
                      onClick={handleCloseMemo}
                      className="font-mono text-[10px] uppercase tracking-[0.22em] text-oxford/50 hover:text-oxford transition-colors"
                      aria-label="Close memo"
                    >
                      Close
                    </button>
                  </div>
                </div>
                <div className="flex-1 min-h-0 flex flex-col px-6 sm:px-8 py-6">
                  <InvestmentMemoContent ref={memoContentRef} startup={selectedStartup} embedded />
                </div>
              </>
            ) : (
              <div className="flex-1 flex items-center justify-center p-8">
                <p className="font-mono text-[10px] uppercase tracking-[0.22em] text-oxford/40">
                  Select a company or show judgements
                </p>
              </div>
            )}
          </aside>
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
            <div className="flex-none p-4 sm:p-5 flex items-center justify-between border-b border-oxford/[0.06]">
              <h2 className="font-mono text-[11px] uppercase tracking-[0.16em] text-oxford/60">
                {judgementsAsOverlay ? 'Judgements' : 'System'}
              </h2>
              <button
                type="button"
                onClick={judgementsAsOverlay ? handleCloseJudgements : () => setRightPanel(null)}
                className="min-w-[44px] min-h-[44px] flex items-center justify-center font-sans text-xl text-oxford/60 hover:text-oxford transition-colors"
                aria-label={judgementsAsOverlay ? 'Close judgements panel' : 'Close system panel'}
              >
                ×
              </button>
            </div>
            <div className="flex-1 min-h-0 overflow-hidden">
              {judgementsAsOverlay ? (
                <LiveIntelligenceFeed startups={startups} />
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
            </div>
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
