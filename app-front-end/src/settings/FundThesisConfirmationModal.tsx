import { useEffect, useRef } from 'react';
import { createPortal } from 'react-dom';
import { AnimatePresence, motion } from 'framer-motion';
import { useFocusTrap, usePrefersReducedMotion } from '../hooks';
import type { FundThesisChange } from './settingsModel';

interface FundThesisConfirmationModalProps {
  open: boolean;
  changes: FundThesisChange[];
  firstPublication: boolean;
  busy: boolean;
  onCancel: () => void;
  onConfirm: () => void;
}

const EASE_OUT = [0.16, 1, 0.3, 1] as const;

export default function FundThesisConfirmationModal({
  open,
  changes,
  firstPublication,
  busy,
  onCancel,
  onConfirm,
}: FundThesisConfirmationModalProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const confirmRef = useRef<HTMLButtonElement>(null);
  const restoreFocusRef = useRef<HTMLElement | null>(null);
  const reduceMotion = usePrefersReducedMotion();
  useFocusTrap(open, containerRef);

  useEffect(() => {
    if (open) {
      restoreFocusRef.current = document.activeElement as HTMLElement | null;
      const frame = requestAnimationFrame(() => confirmRef.current?.focus());
      return () => cancelAnimationFrame(frame);
    }
    restoreFocusRef.current?.focus?.();
  }, [open]);

  useEffect(() => {
    if (!open || busy) return;
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') onCancel();
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [busy, onCancel, open]);

  if (typeof document === 'undefined') return null;

  return createPortal(
    <AnimatePresence>
      {open ? (
        <motion.div
          ref={containerRef}
          key="fund-thesis-confirmation"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: reduceMotion ? 0 : 0.32, ease: EASE_OUT }}
          className="paper-dot-grid fixed inset-0 z-[9999] min-h-0 overflow-y-auto overscroll-contain bg-paper text-oxford"
          role="dialog"
          aria-modal="true"
          aria-labelledby="fund-thesis-confirmation-title"
          aria-describedby="fund-thesis-confirmation-description"
        >
          <div className="relative z-10 flex min-h-full w-full flex-col items-center justify-center px-phi-6 py-phi-7">
            <motion.p
              initial={{ opacity: 0, transform: 'translateY(10px)' }}
              animate={{ opacity: 1, transform: 'translateY(0)' }}
              transition={{ duration: reduceMotion ? 0 : 0.5, ease: EASE_OUT, delay: reduceMotion ? 0 : 0.08 }}
              className="type-label-section mb-phi-3 text-center"
            >
              Policy deployment
            </motion.p>
            <motion.h1
              id="fund-thesis-confirmation-title"
              initial={{ opacity: 0, transform: 'translateY(10px)' }}
              animate={{ opacity: 1, transform: 'translateY(0)' }}
              transition={{ duration: reduceMotion ? 0 : 0.5, ease: EASE_OUT, delay: reduceMotion ? 0 : 0.14 }}
              className="type-display m-0 max-w-[15ch] text-center text-[clamp(28px,4vw,52px)] font-medium leading-[1.1] text-oxford"
            >
              Confirm policy changes
            </motion.h1>
            <motion.p
              id="fund-thesis-confirmation-description"
              initial={{ opacity: 0, transform: 'translateY(10px)' }}
              animate={{ opacity: 1, transform: 'translateY(0)' }}
              transition={{ duration: reduceMotion ? 0 : 0.5, ease: EASE_OUT, delay: reduceMotion ? 0 : 0.22 }}
              className="mt-phi-3 max-w-[48ch] text-center type-body text-oxford/60"
            >
              {firstPublication
                ? 'You are publishing your first fund thesis and scoring policy. Scouting, review, and investment recommendations will use them as soon as deployment completes.'
                : 'This will publish the updated fund thesis and scoring policy. Scouting, review, and investment recommendations will use them as soon as deployment completes.'}
            </motion.p>
            <motion.div
              initial={{ opacity: 0, transform: 'translateY(10px)' }}
              animate={{ opacity: 1, transform: 'translateY(0)' }}
              transition={{ duration: reduceMotion ? 0 : 0.5, ease: EASE_OUT, delay: reduceMotion ? 0 : 0.32 }}
              className="focus-frame mt-phi-7 min-w-0 w-full max-w-3xl bg-paper"
            >
              <div
                data-testid="desktop-comparison-headings"
                className="hidden gap-x-phi-4 border-b border-oxford/[0.16] px-phi-5 py-phi-3 md:grid md:grid-cols-[minmax(9rem,22%)_minmax(0,1fr)_minmax(0,1fr)]"
              >
                <span aria-hidden />
                <p className="type-label-section text-oxford/55">Currently live</p>
                <p className="type-label-section text-oxford">Proposed</p>
              </div>
              {changes.map((change) => (
                <section
                  key={change.key}
                  className="grid min-w-0 grid-cols-1 gap-y-phi-3 border-b border-oxford/[0.06] px-phi-5 py-phi-4 last:border-b-0 md:grid-cols-[minmax(9rem,22%)_minmax(0,1fr)_minmax(0,1fr)] md:gap-x-phi-5 md:gap-y-0"
                  aria-labelledby={`thesis-change-${change.key}`}
                >
                  <h2
                    id={`thesis-change-${change.key}`}
                    className="min-w-0 break-words type-body-emphasis [overflow-wrap:anywhere]"
                  >
                    {change.label}
                  </h2>
                  <div className="min-w-0">
                    <p className="mb-1 type-label-section text-oxford/55 md:hidden">Currently live</p>
                    <p className="whitespace-pre-wrap break-words type-body-sm leading-relaxed text-oxford/55 [overflow-wrap:anywhere]">
                      {change.previous}
                    </p>
                  </div>
                  <div className="min-w-0">
                    <p className="mb-1 type-label-section text-oxford md:hidden">Proposed</p>
                    <p className="whitespace-pre-wrap break-words type-body-sm leading-relaxed text-oxford [overflow-wrap:anywhere]">
                      {change.proposed}
                    </p>
                  </div>
                </section>
              ))}
            </motion.div>
            <motion.div
              initial={{ opacity: 0, transform: 'translateY(10px)' }}
              animate={{ opacity: 1, transform: 'translateY(0)' }}
              transition={{ duration: reduceMotion ? 0 : 0.5, ease: EASE_OUT, delay: reduceMotion ? 0 : 0.42 }}
              className="mt-phi-7 flex w-full max-w-sm flex-col items-center gap-phi-4"
            >
              <button
                ref={confirmRef}
                type="button"
                onClick={onConfirm}
                disabled={busy}
                className="w-full btn-aethria-solid disabled:cursor-not-allowed disabled:opacity-40"
              >
                {busy ? 'Deploying policy…' : 'Deploy policy changes'}
              </button>
              <button
                type="button"
                onClick={onCancel}
                disabled={busy}
                className="type-action inline-flex min-h-11 items-center justify-center px-phi-3 text-oxford/60 transition-colors hover:text-oxford disabled:cursor-not-allowed disabled:opacity-40 focus:outline-none focus-visible:ring-2 focus-visible:ring-oxford/30"
              >
                <span className="border-b border-oxford/10 pb-0.5 transition-colors hover:border-oxford/40">
                  Go back
                </span>
              </button>
            </motion.div>
          </div>
        </motion.div>
      ) : null}
    </AnimatePresence>,
    document.body,
  );
}
