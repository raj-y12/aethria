import { useState, useRef, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { tokens } from '../design-system/tokens';
import GlobalClock from './GlobalClock';
import SystemBar from './SystemBar';
import WorkGrid from './WorkGrid';
import InvestmentMemo from './InvestmentMemo';
import VerdictModal from './VerdictModal';
import LiveIntelligenceFeed from './LiveIntelligenceFeed';
import NoiseOverlay from './NoiseOverlay';
import GhostTransition from './GhostTransition';
import { ContentColumn } from '../layout';
import {
  useScrollLock,
  useEscapeKey,
  useRestoreFocus,
  useFocusTrap,
} from '../hooks';
import type { Startup } from '../types/startup';

interface MainLayoutProps {
  startups: Startup[];
}

export default function MainLayout({ startups }: MainLayoutProps) {
  const [selectedStartup, setSelectedStartup] = useState<Startup | null>(null);
  const [showVerdict, setShowVerdict] = useState(false);
  const [showJudgements, setShowJudgements] = useState(false);

  const restoreRefVerdictMemo = useRef<HTMLElement | null>(null);
  const restoreRefJudgements = useRef<HTMLElement | null>(null);
  const judgementsToggleRef = useRef<HTMLButtonElement | null>(null);
  const judgementsPanelRef = useRef<HTMLDivElement | null>(null);

  const verdictOpen = !!(
    selectedStartup &&
    showVerdict &&
    selectedStartup.partner
  );
  const memoOpen = !!(selectedStartup && !showVerdict);
  const verdictOrMemoOpen = verdictOpen || memoOpen;
  const anyOverlayOpen = verdictOrMemoOpen || showJudgements;

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
  useRestoreFocus(verdictOrMemoOpen, restoreRefVerdictMemo, !showJudgements);
  useRestoreFocus(showJudgements, restoreRefJudgements, !verdictOrMemoOpen);
  useFocusTrap(showJudgements, judgementsPanelRef);

  return (
    <div className="min-h-screen bg-ivory text-charcoal relative">
      <NoiseOverlay />
      <GlobalClock />
      <SystemBar scoutCount={startups.length} />

      <main className="pt-24 lg:pt-28 pb-20 sm:pb-12">
        <ContentColumn variant="panel">
          <GhostTransition>
            <WorkGrid startups={startups} onStartupClick={handleStartupClick} />
          </GhostTransition>
        </ContentColumn>
      </main>

      <button
        ref={judgementsToggleRef}
        type="button"
        onClick={handleToggleJudgements}
        className="fixed bottom-4 right-4 sm:bottom-6 sm:right-6 z-40 min-h-[44px] min-w-[44px] flex items-center justify-center font-sans text-[10px] xs:text-[11px] uppercase tracking-[0.12em] text-charcoal/50 hover:text-charcoal active:opacity-80 transition-colors duration-300 rounded-none"
        aria-pressed={showJudgements}
        aria-expanded={showJudgements}
      >
        {showJudgements ? 'Hide' : 'Show'} judgements
      </button>

      <AnimatePresence mode="wait">
        {showJudgements && (
          <motion.div
            ref={judgementsPanelRef}
            initial={{ x: '100%' }}
            animate={{ x: 0 }}
            exit={{ x: '100%' }}
            transition={{ duration: tokens.motion.duration.medium, ease: tokens.motion.ease }}
            className="fixed top-0 right-0 w-full max-w-full sm:w-[380px] lg:w-[400px] h-full bg-ivory border-l border-oxford/[0.08] z-[60] flex flex-col"
          >
            <div className="flex-none p-3 sm:p-4 border-b border-oxford/[0.08] flex items-center justify-between">
              <h2 className="font-sans font-medium text-[13px] uppercase tracking-tight text-charcoal">
                Judgements
              </h2>
              <button
                type="button"
                onClick={handleCloseJudgements}
                className="min-w-[44px] min-h-[44px] flex items-center justify-center text-charcoal/60 hover:text-charcoal active:opacity-80 font-sans text-xl transition-opacity duration-300"
                aria-label="Close judgements panel"
              >
                ×
              </button>
            </div>
            <div className="flex-1 min-h-0 overflow-hidden">
              <LiveIntelligenceFeed startups={startups} />
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      <AnimatePresence initial={false}>
        {selectedStartup && showVerdict && selectedStartup.partner && (
          <VerdictModal
            key="verdict"
            partner={selectedStartup.partner}
            startupName={selectedStartup.scout.name}
            qualityVerdict={selectedStartup.review?.verdict}
            onClose={handleCloseMemo}
            onViewMemo={() => setShowVerdict(false)}
          />
        )}
        {selectedStartup && !showVerdict && (
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
