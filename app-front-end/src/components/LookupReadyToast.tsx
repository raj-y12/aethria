import { createPortal } from 'react-dom';
import { motion, AnimatePresence } from 'framer-motion';
import DecisionBadge from './DecisionBadge';

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
          <div className="pointer-events-auto grid w-full max-w-[min(92vw,36rem)] gap-phi-3 bg-oxford px-phi-4 py-phi-4 text-paper shadow-[0_12px_36px_rgba(0,20,51,0.18)] sm:grid-cols-[minmax(0,1fr)_auto] sm:items-center sm:gap-phi-5 sm:px-phi-5">
            <div className="min-w-0">
              <div className="flex items-center gap-phi-2 type-status text-paper/65">
                <span className="h-1.5 w-1.5 shrink-0 bg-paper signal-dot-breathe" aria-hidden />
                <span>Memo ready</span>
                {recommendation ? <span aria-hidden>·</span> : null}
                {recommendation ? <span>{recommendation}</span> : null}
              </div>
              <p className="mt-phi-1 truncate font-display text-[1.35rem] leading-tight text-paper sm:text-[1.5rem]">{name}</p>
              <p className="mt-phi-1 type-body-sm text-paper/65">Your investment memo is ready to review.</p>
            </div>
            <div className="flex items-center justify-between gap-phi-3 sm:justify-end">
              {recommendation ? <DecisionBadge variant={recommendation} /> : null}
              <button
                type="button"
                onClick={onOpen}
                className="type-action inline-flex h-[34px] shrink-0 items-center justify-center bg-paper px-phi-4 text-oxford transition-[background-color,transform] duration-150 hover:bg-paper-bright active:scale-[0.98] btn-interaction focus:outline-none focus-visible:ring-2 focus-visible:ring-paper/70 motion-reduce:transition-none motion-reduce:active:scale-100"
              >
                Open memo
              </button>
              <button
                type="button"
                onClick={onDismiss}
                aria-label="Dismiss memo ready notification"
                className="shrink-0 cursor-pointer border-0 bg-transparent p-1 text-lg leading-none text-paper/60 transition-colors hover:text-paper btn-interaction focus:outline-none focus-visible:ring-2 focus-visible:ring-paper/70"
              >
                ×
              </button>
            </div>
          </div>
        </motion.div>
      ) : null}
    </AnimatePresence>
  );

  if (typeof document === 'undefined') return null;
  return createPortal(toast, document.body);
}
