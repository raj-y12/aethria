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
          className="pointer-events-none fixed inset-x-0 bottom-phi-5 z-[9998] flex justify-center px-phi-3"
          role="status"
          aria-live="polite"
        >
          <div className="pointer-events-auto flex w-full max-w-[min(92vw,32rem)] items-center gap-phi-3 rounded-full bg-oxford px-phi-4 py-phi-3 text-paper shadow-[0_10px_28px_rgba(10,22,41,0.2)] sm:gap-phi-4">
            <span className="h-2 w-2 shrink-0 rounded-full bg-paper signal-dot-breathe" aria-hidden />
            <p className="min-w-0 flex-1 truncate font-display text-[15px] leading-none text-paper sm:text-[16px]">
              <span className="sr-only">Memo ready: </span>
              {name}
            </p>
            <div className="flex shrink-0 items-center gap-phi-2">
              {recommendation ? <DecisionBadge variant={recommendation} className="!h-6 !min-w-[4.25rem] !rounded-full !px-2.5" /> : null}
              <button
                type="button"
                onClick={onOpen}
                className="type-action inline-flex h-6 min-w-[4.25rem] shrink-0 items-center justify-center rounded-full bg-paper px-phi-4 text-[10px] text-oxford transition-[background-color,transform] duration-150 hover:bg-paper-bright active:scale-[0.98] btn-interaction focus:outline-none focus-visible:ring-2 focus-visible:ring-paper/70 motion-reduce:transition-none motion-reduce:active:scale-100"
              >
                Open memo
              </button>
              <button type="button" onClick={onDismiss} aria-label="Dismiss memo ready notification" className="shrink-0 cursor-pointer border-0 bg-transparent p-1 text-base leading-none text-paper/50 transition-colors hover:text-paper btn-interaction focus:outline-none focus-visible:ring-2 focus-visible:ring-paper/70">×</button>
            </div>
          </div>
        </motion.div>
      ) : null}
    </AnimatePresence>
  );

  if (typeof document === 'undefined') return null;
  return createPortal(toast, document.body);
}
