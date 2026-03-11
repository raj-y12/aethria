import { useState, useRef, useCallback } from 'react';
import { createPortal } from 'react-dom';
import { motion, AnimatePresence } from 'framer-motion';
import { tokens } from '../design-system/tokens';
import SystemBar from './SystemBar';
import AppFooter from './AppFooter';
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
  const restoreRefVerdictMemo = useRef<HTMLElement | null>(null);
  const judgementsPanelRef = useRef<HTMLDivElement | null>(null);
  const memoContentRef = useRef<InvestmentMemoContentHandle | null>(null);

  const memoOpen = !!selectedStartup;
  const verdictOrMemoOpen = memoOpen;
  const judgementsAsOverlay = rightPanel === 'feed' && !isDesktop;
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

  return (
    <div className="min-h-[100dvh] flex flex-col overflow-hidden bg-paper">
      <SystemBar
        scoutCount={startups.length}
        rightPanel={rightPanel}
        onShowFeed={() => setRightPanel((panel) => (panel === 'feed' ? null : 'feed'))}
        onShowSystem={() => setRightPanel((panel) => (panel === 'system' ? null : 'system'))}
        onClose={() => setRightPanel(null)}
      />
      {startupsError && (
        <div className="flex-none px-6 py-2 bg-amber-100 text-amber-900 font-mono text-[10px] uppercase tracking-wider">
          {startupsError} — Check API URL (VITE_API_URL) and backend CORS (ALLOWED_ORIGINS).
        </div>
      )}

      {/* Paper canvas. Fixed height so only WorkGrid scrolls. Safe area for notched devices. */}
      <main
        className="flex-1 flex flex-col min-h-0 overflow-hidden"
        style={{ paddingTop: 'calc(56px + max(24px, env(safe-area-inset-top)))' }}
      >
        <div
          className="flex-1 flex flex-col lg:grid lg:grid-cols-[3fr_2fr] min-h-0 overflow-hidden pb-3 lg:pb-4 gap-6 lg:gap-10"
          style={{
            paddingLeft: 'max(24px, env(safe-area-inset-left))',
            paddingRight: 'max(24px, env(safe-area-inset-right))',
            paddingTop: '24px',
          }}
        >
          <div className="flex flex-col min-w-0 min-h-0">
            {/* System health (same style as Settings page) */}
            <section className="flex-none py-4 border-b border-oxford/[0.06]">
              <h2 className="font-mono text-[11px] uppercase tracking-[0.16em] text-oxford/60 mb-2">
                System health
              </h2>
              {data.settings?.system_health ? (
                <div className="space-y-1">
                  <p className="font-mono text-[10px] uppercase tracking-[0.16em] tabular-nums text-oxford/50">
                    {startups.length} companies · {resolvedCount} decided
                  </p>
                  {data.settings.system_health.pending_escalations > 0 && (
                    <p className="font-mono text-[11px] uppercase tracking-[0.16em] text-oxford flex items-center gap-2">
                      <span className="w-1.5 h-1.5 bg-oxford escalation-pulse" aria-hidden />
                      <span>
                        {data.settings.system_health.pending_escalations}{' '}
                        {data.settings.system_health.pending_escalations === 1 ? 'escalation' : 'escalations'} awaiting review
                      </span>
                    </p>
                  )}
                  {data.settings.system_health.calibration_warning && (
                    <p className="font-mono text-[11px] uppercase tracking-[0.16em] text-oxford/70">
                      • Calibration: {data.settings.system_health.calibration_warning}
                    </p>
                  )}
                  {data.settings.system_health.queue_depths && (
                    <p className="font-mono text-[10px] uppercase tracking-[0.16em] text-oxford/50">
                      Unreviewed {data.settings.system_health.queue_depths.unreviewed} · Undecided{' '}
                      {data.settings.system_health.queue_depths.undecided} · Watchlist{' '}
                      {data.settings.system_health.queue_depths.watchlist}
                    </p>
                  )}
                </div>
              ) : (
                <div className="space-y-1">
                  <p className="font-mono text-[10px] uppercase tracking-[0.16em] tabular-nums text-oxford/50">
                    {startups.length} companies · {resolvedCount} decided
                  </p>
                  <p className="font-mono text-[10px] uppercase tracking-[0.16em] text-oxford/40">
                    System health metrics are not available yet.
                  </p>
                </div>
              )}
            </section>

            {/* WorkGrid: only this area scrolls; fills column so both columns resize together */}
            <div className="flex-1 min-h-0 overflow-y-auto w-full min-w-0 rounded-none border border-oxford/[0.06] bg-paper">
              <div className="px-6 sm:px-8 lg:px-10 pt-2 pb-6 lg:pb-8">
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

      <AppFooter navLink={{ href: '/settings', label: 'Settings' }} />

      {/* Judgements as slide-over only on mobile; on desktop they appear in the right panel. */}
      {judgementsAsOverlay && typeof document !== 'undefined' && createPortal(
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
            onClick={handleCloseJudgements}
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
                Judgements
              </h2>
              <button
                type="button"
                onClick={handleCloseJudgements}
                className="min-w-[44px] min-h-[44px] flex items-center justify-center font-sans text-xl text-oxford/60 hover:text-oxford transition-colors"
                aria-label="Close judgements panel"
              >
                ×
              </button>
            </div>
            <div className="flex-1 min-h-0 overflow-hidden">
              <LiveIntelligenceFeed startups={startups} />
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
