import { createPortal } from 'react-dom';
import { motion, AnimatePresence } from 'framer-motion';

const EASE = [0.16, 1, 0.3, 1] as const;

interface LookupReadyToastProps {
  /** Company name when a background lookup has finished and is unopened. Null hides the toast. */
  name: string | null;
  recommendation?: 'INVEST' | 'PASS' | 'MONITOR' | null;
  onOpen: () => void;
  onDismiss: () => void;
}

/**
 * Non-modal "ready" toast. Surfaces a background lookup that finished while the
 * analyst kept working, so they're notified without being interrupted.
 */
export default function LookupReadyToast({ name, recommendation, onOpen, onDismiss }: LookupReadyToastProps) {
  const toast = (
    <AnimatePresence>
      {name ? (
        // Fixed, full-width centering rail. Centering lives here (flex justify-center)
        // so it can't be clobbered by framer-motion writing `transform` for the y slide.
        <motion.div
          key="lookup-ready"
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: 16 }}
          transition={{ duration: 0.28, ease: EASE }}
          className="pointer-events-none fixed inset-x-0 bottom-phi-5 z-[9998] flex justify-center px-phi-4"
          role="status"
          aria-live="polite"
        >
          <div className="pointer-events-auto flex max-w-[min(92vw,30rem)] items-center gap-phi-4 border border-oxford/25 bg-paper-bright px-phi-5 py-phi-3">
            <span className="h-1.5 w-1.5 shrink-0 rounded-none bg-oxford signal-dot-breathe" aria-hidden />
            <span className="min-w-0 flex-1">
              <span className="type-status block">
                Lookup ready{recommendation ? ` · ${recommendation}` : ''}
              </span>
              <span className="block truncate type-body-sm font-medium text-oxford">{name}</span>
            </span>
            <button
              type="button"
              onClick={onOpen}
              className="type-action inline-flex h-[34px] shrink-0 items-center justify-center bg-oxford px-phi-4 text-paper transition-opacity hover:opacity-90 btn-interaction focus:outline-none focus-visible:ring-2 focus-visible:ring-oxford/35"
            >
              Open memo
            </button>
            <button
              type="button"
              onClick={onDismiss}
              aria-label="Dismiss"
              className="shrink-0 cursor-pointer border-0 bg-transparent p-0 text-base leading-none text-oxford/60 transition-colors hover:text-oxford btn-interaction"
            >
              ×
            </button>
          </div>
        </motion.div>
      ) : null}
    </AnimatePresence>
  );

  if (typeof document === 'undefined') return null;
  return createPortal(toast, document.body);
}
