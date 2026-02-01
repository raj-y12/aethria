import { useRef } from 'react';
import { motion } from 'framer-motion';
import type { Partner } from '../types/startup';
import { tokens } from '../design-system/tokens';
import { verdictTextClass } from '../design-system/verdictTint';
import { QUALITY_LABELS, DECISION_LABELS } from '../design-system/semantics';
import { useFocusTrap } from '../hooks';

interface VerdictModalProps {
  partner: Partner;
  startupName: string;
  qualityVerdict?: string;
  onClose: () => void;
  onViewMemo?: () => void;
}

/**
 * Verdict as logged decision. Close button, click-outside, escape. Focus trap.
 * Exit animation handled by parent AnimatePresence.
 */
export default function VerdictModal({
  partner,
  startupName,
  qualityVerdict,
  onClose,
  onViewMemo,
}: VerdictModalProps) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  useFocusTrap(true, containerRef);

  return (
    <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        transition={{ duration: tokens.motion.duration.medium, ease: tokens.motion.ease }}
      className="fixed inset-0 z-[100] bg-ivory flex items-center justify-center"
      onClick={onClose}
      role="dialog"
      aria-modal="true"
      aria-labelledby="verdict-title"
    >
        <div
          ref={containerRef}
          className="relative z-10 w-full max-w-4xl mx-4 sm:mx-6 max-h-[90vh] overflow-y-auto px-4 xs:px-6 lg:px-10 py-6 sm:py-8"
          onClick={(e) => e.stopPropagation()}
        >
          <p className="font-sans text-[10px] uppercase tracking-[0.14em] text-charcoal/45 mb-1">
            Investment decision
          </p>
          <h1
            id="verdict-title"
            className="font-sans font-medium text-lg lg:text-xl text-charcoal tracking-tight mb-6"
          >
            {startupName}
          </h1>

          <div className="mb-6 pl-4 border-l-2 border-oxford/20">
            {qualityVerdict && (
              <p className="font-sans text-[11px] text-charcoal/50">
                <span className="uppercase tracking-wide">Quality</span> · {qualityVerdict}{' '}
                ({QUALITY_LABELS[qualityVerdict] ?? qualityVerdict})
              </p>
            )}
            <p className={`font-sans text-[11px] mt-1 ${qualityVerdict ? '' : ''}`}>
              <span className="uppercase tracking-wide text-charcoal/50">Investment decision</span> ·{' '}
              <span className={verdictTextClass(partner.decision)}>{partner.decision}</span>{' '}
              ({DECISION_LABELS[partner.decision] ?? partner.decision})
            </p>
            {partner.rationale && (
              <p className="font-sans text-[13px] text-charcoal/75 leading-relaxed mt-3">
                {partner.rationale}
              </p>
            )}
          </div>

          {partner.next_action && (
            <p className="font-sans text-[11px] text-charcoal/50 mb-6">
              Next: {partner.next_action}
            </p>
          )}

          <div className="flex flex-row gap-6">
            <button
              type="button"
              onClick={onClose}
              className="min-h-[44px] px-4 font-sans text-[11px] uppercase tracking-[0.12em] text-charcoal/50 hover:text-charcoal active:opacity-80 transition-colors duration-300"
            >
              Close
            </button>
            {onViewMemo && (
              <button
                type="button"
                onClick={onViewMemo}
                className="min-h-[44px] px-4 font-sans text-[11px] uppercase tracking-[0.12em] text-charcoal/50 hover:text-charcoal active:opacity-80 transition-colors duration-300"
              >
                Full memo
              </button>
            )}
          </div>
        </div>
    </motion.div>
  );
}
