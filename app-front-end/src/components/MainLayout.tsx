import { useState, useRef, useCallback } from 'react';
import { createPortal } from 'react-dom';
import { motion, AnimatePresence } from 'framer-motion';
import { tokens } from '../design-system/tokens';
import SystemBar from './SystemBar';
import AppFooter from './AppFooter';
import WorkGrid from './WorkGrid';
import InvestmentMemo from './InvestmentMemo';
import VerdictModal from './VerdictModal';
import LiveIntelligenceFeed from './LiveIntelligenceFeed';
import GhostTransition from './GhostTransition';
import {
  useScrollLock,
  useEscapeKey,
  useRestoreFocus,
  useFocusTrap,
  useMediaQuery,
} from '../hooks';
import type { Startup } from '../types/startup';
import InvestmentMemoContent, { type InvestmentMemoContentHandle } from './InvestmentMemoContent';

interface MainLayoutProps {
  startups: Startup[];
  startupsError?: string | null;
}

export default function MainLayout({ startups, startupsError }: MainLayoutProps) {
  const [selectedStartup, setSelectedStartup] = useState<Startup | null>(null);
  const [showVerdict, setShowVerdict] = useState(false);
  const [showJudgements, setShowJudgements] = useState(false);

  const isDesktop = useMediaQuery('(min-width: 1024px)');
  const restoreRefVerdictMemo = useRef<HTMLElement | null>(null);
  const restoreRefJudgements = useRef<HTMLElement | null>(null);
  const judgementsToggleRef = useRef<HTMLButtonElement | null>(null);
  const judgementsPanelRef = useRef<HTMLDivElement | null>(null);
  const memoContentRef = useRef<InvestmentMemoContentHandle | null>(null);

  const verdictOpen = !!(
    selectedStartup &&
    showVerdict &&
    selectedStartup.partner
  );
  const memoOpen = !!(selectedStartup && !showVerdict);
  const verdictOrMemoOpen = verdictOpen || memoOpen;
  const judgementsAsOverlay = showJudgements && !isDesktop;
  const anyOverlayOpen = verdictOrMemoOpen || judgementsAsOverlay;
  const useModal = selectedStartup && !isDesktop;

  const handleStartupClick = useCallback((startup: Startup) => {
    restoreRefVerdictMemo.current = document.activeElement as HTMLElement | null;
    setSelectedStartup(startup);
    setShowVerdict(!!startup.partner?.decision);
  }, []);

  const handleCloseMemo = useCallback(() => {
    setSelectedStartup(null);
    setShowVerdict(false);
  }, []);

  const handleCloseJudgements = useCallback(() => {
    setShowJudgements(false);
  }, []);

  const handleEscape = useCallback(() => {
    if (verdictOpen) handleCloseMemo();
    else if (memoOpen) handleCloseMemo();
    else if (showJudgements) handleCloseJudgements();
  }, [verdictOpen, memoOpen, showJudgements, handleCloseMemo, handleCloseJudgements]);

  const handleToggleJudgements = useCallback(() => {
    if (!showJudgements) {
      restoreRefJudgements.current = judgementsToggleRef.current;
    }
    setShowJudgements((v) => !v);
  }, [showJudgements]);

  useScrollLock(anyOverlayOpen);
  useEscapeKey(handleEscape, anyOverlayOpen);
  useRestoreFocus(verdictOrMemoOpen, restoreRefVerdictMemo, !judgementsAsOverlay);
  useRestoreFocus(judgementsAsOverlay, restoreRefJudgements, !verdictOrMemoOpen);
  useFocusTrap(judgementsAsOverlay, judgementsPanelRef);

  const resolvedCount = startups.filter((s) => s.partner?.decision != null).length;

  return (
    <div className="h-screen flex flex-col overflow-hidden bg-paper">
      <SystemBar scoutCount={startups.length} />
      {startupsError && (
        <div className="flex-none px-6 py-2 bg-amber-100 text-amber-900 font-mono text-[10px] uppercase tracking-wider">
          {startupsError} — Check API URL (VITE_API_URL) and backend CORS (ALLOWED_ORIGINS).
        </div>
      )}

      {/* Paper canvas. Fixed height so only WorkGrid scrolls. On lg+: list left, memo panel right. */}
      <main className="flex-1 pt-24 flex flex-col min-h-0 overflow-hidden">
        <div className="flex-1 flex flex-col lg:flex-row min-h-0 overflow-hidden px-6 sm:px-8 lg:px-12 pt-6 lg:pt-8 pb-3 lg:pb-4 gap-6 lg:gap-10">
          <div className="flex flex-col min-w-0 min-h-0 lg:max-w-[56rem] flex-1 lg:flex-initial">
            {/* Fixed header: Evaluations + count + Show judgements (not in scroll area) */}
            <div className="flex-none flex flex-wrap items-baseline justify-between gap-4 pt-4 lg:pt-2 pb-5 lg:pb-4 bg-paper shrink-0">
              <div>
                <p className="font-mono text-[10px] uppercase tracking-[0.22em] text-oxford/60">
                  Evaluations
                </p>
                <p className="font-mono text-[10px] uppercase tracking-[0.22em] mt-0.5 tabular-nums text-oxford/50">
                  {startups.length} companies · {resolvedCount} decided
                </p>
              </div>
              <button
                ref={judgementsToggleRef}
                type="button"
                onClick={handleToggleJudgements}
                className="font-mono text-[10px] uppercase tracking-[0.22em] text-oxford/60 hover:text-oxford transition-colors"
                aria-pressed={showJudgements}
                aria-expanded={showJudgements}
              >
                {showJudgements ? 'Hide' : 'Show'} judgements
              </button>
            </div>

            {/* WorkGrid: only this area scrolls */}
            <div className="flex-1 min-h-0 overflow-y-auto w-full max-w-4xl rounded-none border border-oxford/[0.06] bg-paper shrink-0">
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

          {/* Right panel on desktop: Judgements (when toggled) or Memo (when company selected) or empty. */}
          <aside
            className="hidden lg:flex flex-col min-w-0 flex-1 min-h-0 border border-oxford/[0.06] bg-paper overflow-hidden"
            aria-live="polite"
            aria-label={showJudgements ? 'Judgements' : selectedStartup ? 'Investment memo' : 'Detail'}
          >
            {showJudgements ? (
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
            className="fixed top-0 right-0 w-full max-w-full sm:w-[380px] lg:w-[400px] h-full z-[10000] flex flex-col bg-paper"
            style={{ borderLeft: tokens.frameBorder, minHeight: '100dvh' }}
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

      {/* Modals only on small viewports; on desktop the right panel shows the memo. */}
      <AnimatePresence initial={false}>
        {useModal && selectedStartup && showVerdict && selectedStartup.partner && (
          <VerdictModal
            key="verdict"
            partner={selectedStartup.partner}
            startupName={selectedStartup.scout.name}
            qualityVerdict={selectedStartup.review?.verdict}
            onClose={handleCloseMemo}
            onViewMemo={() => setShowVerdict(false)}
          />
        )}
        {useModal && selectedStartup && !showVerdict && (
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
