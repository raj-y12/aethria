import { useRef } from 'react';
import { createPortal } from 'react-dom';
import { motion } from 'framer-motion';
import type { Startup } from '../types/startup';
import { tokens } from '../design-system/tokens';
import { chrome } from '../design-system/chrome';
import { transitionOrReduced } from '../design-system/motion';
import { useFocusTrap, usePrefersReducedMotion } from '../hooks';
import InvestmentMemoContent from './InvestmentMemoContent';

interface InvestmentMemoProps {
  startup: Startup | null;
  onClose: () => void;
}

/**
 * Full-screen modal wrapper for the investment memo. Used on small viewports.
 */
export default function InvestmentMemo({ startup, onClose }: InvestmentMemoProps) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const reduceMotion = usePrefersReducedMotion();
  useFocusTrap(true, containerRef);

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
      className="fixed inset-0 z-[9999] flex items-start justify-center"
      style={{
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
        className={`relative z-10 mx-auto flex max-h-[85vh] w-full max-w-[420px] flex-col overflow-y-auto overflow-x-hidden px-4 py-6 sm:max-h-[90vh] sm:max-w-3xl sm:px-6 sm:py-8 lg:px-10 ${chrome.frame}`}
        onClick={(e) => e.stopPropagation()}
      >
        <InvestmentMemoContent startup={startup} onClose={onClose} />
      </div>
    </motion.div>
  );

  if (typeof document === 'undefined') return null;
  return createPortal(content, document.body);
}
