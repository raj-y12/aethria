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
          className="fixed inset-0 z-[9999] flex min-h-0 flex-col bg-paper text-oxford"
          role="dialog"
          aria-modal="true"
          aria-labelledby="fund-thesis-confirmation-title"
          aria-describedby="fund-thesis-confirmation-description"
        >
          <header className="shrink-0 border-b border-oxford/[0.08] px-phi-5 py-phi-5 lg:px-phi-7">
            <div className="mx-auto w-full max-w-[72rem]">
              <motion.p
                initial={{ opacity: 0, transform: 'translateY(8px)' }}
                animate={{ opacity: 1, transform: 'translateY(0)' }}
                transition={{ duration: reduceMotion ? 0 : 0.4, ease: EASE_OUT, delay: reduceMotion ? 0 : 0.04 }}
                className="type-label-section text-oxford/60"
              >
                Deployment review
              </motion.p>
              <motion.h1
                id="fund-thesis-confirmation-title"
                initial={{ opacity: 0, transform: 'translateY(10px)' }}
                animate={{ opacity: 1, transform: 'translateY(0)' }}
                transition={{ duration: reduceMotion ? 0 : 0.45, ease: EASE_OUT, delay: reduceMotion ? 0 : 0.08 }}
                className="type-display mt-phi-2 max-w-[22ch] text-[clamp(28px,4vw,48px)] leading-[1.08] text-oxford"
              >
                Confirm fund thesis change<span className="wordmark-dot">.</span>
              </motion.h1>
              <motion.p
                id="fund-thesis-confirmation-description"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                transition={{ duration: reduceMotion ? 0 : 0.4, ease: EASE_OUT, delay: reduceMotion ? 0 : 0.14 }}
                className="mt-phi-3 max-w-[65ch] type-body-sm leading-relaxed text-oxford/65"
              >
                {firstPublication
                  ? 'You are publishing your first fund thesis. Scouts and Reviewers will use it as soon as deployment completes.'
                  : 'Scouts and Reviewers will use the proposed thesis as soon as deployment completes. Review each change before continuing.'}
              </motion.p>
            </div>
          </header>

          <div className="min-h-0 flex-1 overflow-y-auto px-phi-5 py-phi-6 lg:px-phi-7 lg:py-phi-7">
            <motion.div
              initial={{ opacity: 0, transform: 'translateY(10px)' }}
              animate={{ opacity: 1, transform: 'translateY(0)' }}
              transition={{ duration: reduceMotion ? 0 : 0.45, ease: EASE_OUT, delay: reduceMotion ? 0 : 0.18 }}
              className="mx-auto w-full max-w-[72rem]"
              aria-label="Fund thesis changes"
            >
              <div className="grid grid-cols-2 gap-x-phi-4 border-b border-oxford/[0.08] pb-phi-2 md:grid-cols-[minmax(10rem,20%)_minmax(0,1fr)_minmax(0,1fr)] md:gap-x-phi-7">
                <span className="hidden md:block" aria-hidden />
                <p className="type-label-section text-oxford/55">Currently live</p>
                <p className="type-label-section text-oxford">Proposed</p>
              </div>
              <div>
                {changes.map((change) => (
                  <section
                    key={change.key}
                    className="grid gap-y-phi-2 border-b border-oxford/[0.06] py-phi-4 md:grid-cols-[minmax(10rem,20%)_minmax(0,1fr)_minmax(0,1fr)] md:gap-x-phi-7 md:py-phi-5"
                    aria-labelledby={`thesis-change-${change.key}`}
                  >
                    <h2
                      id={`thesis-change-${change.key}`}
                      className="col-span-2 type-body-emphasis text-oxford md:col-span-1"
                    >
                      {change.label}
                    </h2>
                    <p className="whitespace-pre-wrap break-words type-body-sm leading-relaxed text-oxford/55">
                      {change.previous}
                    </p>
                    <p className="whitespace-pre-wrap break-words type-body-sm leading-relaxed text-oxford">
                      {change.proposed}
                    </p>
                  </section>
                ))}
              </div>
            </motion.div>
          </div>

          <footer className="shrink-0 border-t border-oxford/[0.08] bg-paper px-phi-5 py-phi-4 lg:px-phi-7">
            <div className="mx-auto flex w-full max-w-[72rem] flex-col-reverse gap-phi-3 sm:flex-row sm:items-center sm:justify-end">
              <button
                type="button"
                onClick={onCancel}
                disabled={busy}
                className="type-action inline-flex min-h-11 items-center justify-center px-phi-4 transition-colors hover:text-oxford disabled:cursor-not-allowed disabled:opacity-40 btn-interaction focus:outline-none focus-visible:ring-2 focus-visible:ring-oxford/30"
              >
                Go back
              </button>
              <button
                ref={confirmRef}
                type="button"
                onClick={onConfirm}
                disabled={busy}
                className="btn-aethria-solid min-w-[15rem] disabled:cursor-not-allowed disabled:opacity-40"
              >
                {busy ? 'Updating fund thesis…' : 'Yes, update fund thesis'}
              </button>
            </div>
          </footer>
        </motion.div>
      ) : null}
    </AnimatePresence>,
    document.body,
  );
}
