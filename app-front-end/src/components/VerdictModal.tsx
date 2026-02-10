import { useRef } from 'react';
import { createPortal } from 'react-dom';
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
 * Rendered via portal so overlay sits on top of the whole page.
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

  const content = (
    <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        transition={{ duration: tokens.motion.duration.medium, ease: tokens.motion.ease }}
      className="fixed inset-0 z-[9999] flex items-center justify-center"
      style={{
        minHeight: '100dvh',
        width: '100vw',
        left: 0,
        top: 0,
        right: 0,
        bottom: 0,
        backgroundColor: '#F2F0EA',
      }}
      onClick={onClose}
      role="dialog"
      aria-modal="true"
      aria-labelledby="verdict-title"
    >
        <div
          ref={containerRef}
          className="relative z-10 w-full max-w-4xl mx-4 sm:mx-6 max-h-[90vh] overflow-y-auto bg-paper"
          onClick={(e) => e.stopPropagation()}
        >
          {/* Slim oxford accent — decision only */}
          <div className="flex items-center px-4 xs:px-6 lg:px-10 py-3 bg-oxford border-b border-white/[0.06]">
            <span className="font-mono text-[10px] uppercase tracking-[0.22em] text-ivory/70">
              Decision
            </span>
            <span className={verdictTextClass(partner.decision, true) + ' font-mono text-[11px] uppercase tracking-[0.16em] ml-3'}>
              {DECISION_LABELS[partner.decision] ?? partner.decision}
            </span>
          </div>

          <div className="px-4 xs:px-6 lg:px-10 py-6 sm:py-8">
          <h1
            id="verdict-title"
            className="font-sans font-semibold text-lg lg:text-xl text-oxford tracking-tight mb-4"
            style={{ letterSpacing: '-0.02em' }}
          >
            {startupName}
          </h1>

          <div className="mb-6 pl-4 border-l-2 border-oxford/20">
            {qualityVerdict && (
              <p className="font-mono text-[10px] uppercase tracking-[0.22em] text-oxford/60">
                Quality · {qualityVerdict} ({QUALITY_LABELS[qualityVerdict] ?? qualityVerdict})
              </p>
            )}
            <p className="font-mono text-[10px] uppercase tracking-[0.22em] mt-1">
              <span className="text-oxford/60">Investment decision</span> ·{' '}
              <span className={verdictTextClass(partner.decision)}>{partner.decision}</span>{' '}
              ({DECISION_LABELS[partner.decision] ?? partner.decision})
            </p>
            {partner.rationale && (
              <p className="font-sans text-[13px] text-oxford/80 leading-relaxed mt-3">
                {partner.rationale}
              </p>
            )}
          </div>

          {partner.next_action && (
            <p className="font-mono text-[10px] uppercase tracking-[0.22em] text-oxford/60 mb-6">
              Next: {partner.next_action}
            </p>
          )}

          <div className="flex flex-row gap-6">
            <button
              type="button"
              onClick={onClose}
              className="min-h-[44px] px-4 font-mono text-[10px] uppercase tracking-[0.22em] text-oxford/60 hover:text-oxford active:opacity-80 transition-colors duration-300 rounded-none"
            >
              Close
            </button>
            {onViewMemo && (
              <button
                type="button"
                onClick={onViewMemo}
                className="min-h-[44px] px-4 font-mono text-[10px] uppercase tracking-[0.22em] text-oxford/60 hover:text-oxford active:opacity-80 transition-colors duration-300 rounded-none"
              >
                Full memo
              </button>
            )}
          </div>
          </div>
        </div>
    </motion.div>
  );

  if (typeof document === 'undefined') return null;
  return createPortal(content, document.body);
}
