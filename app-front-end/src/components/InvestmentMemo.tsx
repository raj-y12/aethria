import { useEffect, useRef } from 'react';
import { createPortal } from 'react-dom';
import { motion } from 'framer-motion';
import type { SignalItem, Startup } from '../types/startup';
import type { FundConfiguration } from '../lib/fundConfiguration';
import { tokens } from '../design-system/tokens';
import { chrome } from '../design-system/chrome';
import { transitionOrReduced } from '../design-system/motion';
import { useFocusTrap, usePrefersReducedMotion } from '../hooks';
import InvestmentMemoContent from './InvestmentMemoContent';
import type { MemoDecisionBriefStatus } from '../lib/memoDecisionBrief';

interface InvestmentMemoProps {
  startup: Startup | null;
  onClose: () => void;
  onAddContext?: () => void;
  onMemoPipelineReady?: () => void;
  onDecisionResolved?: (startup: Startup) => void;
  fundConfiguration?: FundConfiguration;
  peerStartups?: Startup[];
  portfolioSignals?: SignalItem[];
  onDecisionStatusChange?: (status: MemoDecisionBriefStatus) => void;
}

/**
 * Full-screen modal wrapper for the investment memo. Used on small viewports.
 */
export default function InvestmentMemo({ startup, onClose, onAddContext, onMemoPipelineReady, onDecisionResolved, fundConfiguration, peerStartups, portfolioSignals, onDecisionStatusChange }: InvestmentMemoProps) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const reduceMotion = usePrefersReducedMotion();
  useFocusTrap(true, containerRef);

  useEffect(() => {
    if (!startup) return;
    const handleEscape = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    document.addEventListener('keydown', handleEscape);
    return () => document.removeEventListener('keydown', handleEscape);
  }, [startup, onClose]);

  if (!startup) return null;

  const content = (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      transition={transitionOrReduced(reduceMotion, {
        duration: tokens.motion.duration.medium,
        ease: tokens.motion.ease,
      })}
      className="fixed inset-0 flex items-start justify-center"
      style={{
        zIndex: tokens.layout.modalLayerZ,
        minHeight: '100dvh',
        width: '100vw',
        left: 0,
        top: 0,
        right: 0,
        bottom: 0,
        backgroundColor: tokens.color.paper,
        paddingTop: 'max(24px, env(safe-area-inset-top))',
        paddingBottom: 'env(safe-area-inset-bottom)',
        paddingLeft: 'env(safe-area-inset-left)',
        paddingRight: 'env(safe-area-inset-right)',
      }}
      onClick={onClose}
      role="dialog"
      aria-modal="true"
      aria-labelledby="memo-title"
    >
      <div
        ref={containerRef}
        className={`relative z-10 mx-auto flex w-full flex-col overflow-y-auto overflow-x-hidden px-3 py-4 sm:px-8 sm:py-9 lg:px-12 ${chrome.frame}`}
        style={{
          maxHeight: tokens.layout.modalMaxHeightDesktop,
          width: `min(100%, clamp(${tokens.layout.modalMaxWidthMobile}, 70vw, ${tokens.layout.modalMaxWidthDesktop}))`,
        }}
        onClick={(e) => e.stopPropagation()}
      >
        <InvestmentMemoContent
          startup={startup}
          onClose={onClose}
          onAddContext={onAddContext}
          onMemoPipelineReady={onMemoPipelineReady}
          onDecisionResolved={onDecisionResolved}
          fundConfiguration={fundConfiguration}
          peerStartups={peerStartups}
          portfolioSignals={portfolioSignals}
          onDecisionStatusChange={onDecisionStatusChange}
        />
      </div>
    </motion.div>
  );

  if (typeof document === 'undefined') return null;
  return createPortal(content, document.body);
}
