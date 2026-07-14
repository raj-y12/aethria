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
          <div className="pointer-events-auto w-full max-w-[min(92vw,30rem)] border border-oxford/20 border-t-2 border-t-oxford bg-paper-bright text-oxford shadow-[0_10px_28px_rgba(0,20,51,0.12)]">
            <div className="flex items-center justify-between border-b border-oxford/10 px-phi-3 py-phi-2 sm:px-phi-4">
              <div className="flex items-center gap-phi-2 type-status text-oxford/55">
                <span className="h-1.5 w-1.5 shrink-0 bg-oxford signal-dot-breathe" aria-hidden />
                <span>Memo ready</span>
              </div>
              <button
                type="button"
                onClick={onDismiss}
                aria-label="Dismiss memo ready notification"
                className="shrink-0 cursor-pointer border-0 bg-transparent p-0 text-base leading-none text-oxford/45 transition-colors hover:text-oxford btn-interaction focus:outline-none focus-visible:ring-2 focus-visible:ring-oxford/45"
              >
                ×
              </button>
            </div>
            <div className="flex items-center gap-phi-3 px-phi-3 py-phi-3 sm:px-phi-4">
              <p className="min-w-0 flex-1 truncate font-sans text-[15px] font-medium leading-tight text-oxford">{name}</p>
              <div className="flex shrink-0 items-center gap-phi-2">
                {recommendation ? <DecisionBadge variant={recommendation} /> : null}
              <button
                type="button"
                onClick={onOpen}
                className="type-action inline-flex h-[32px] shrink-0 items-center justify-center bg-oxford px-phi-3 text-paper transition-[background-color,transform] duration-150 hover:bg-oxford/90 active:scale-[0.98] btn-interaction focus:outline-none focus-visible:ring-2 focus-visible:ring-oxford/45 motion-reduce:transition-none motion-reduce:active:scale-100"
              >
                Open memo
              </button>
              </div>
            </div>
          </div>
        </motion.div>
      ) : null}
    </AnimatePresence>
  );

  if (typeof document === 'undefined') return null;
  return createPortal(toast, document.body);
}
