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
          <div className="pointer-events-auto flex w-full max-w-[min(92vw,32rem)] items-center gap-phi-2 rounded-full bg-oxford px-phi-2 py-phi-2 text-paper shadow-[0_10px_28px_rgba(0,20,51,0.2)] sm:gap-phi-3 sm:px-phi-3">
            <p className="min-w-0 flex-1 truncate pl-phi-2 font-sans text-[13px] font-medium text-paper sm:text-[14px]">
              <span className="sr-only">Memo ready: </span>
              {name}
            </p>
            <div className="flex shrink-0 items-center gap-phi-2">
              <span className="h-1.5 w-1.5 shrink-0 bg-paper signal-dot-breathe" aria-hidden />
              {recommendation ? <DecisionBadge variant={recommendation} className="!h-7 !min-w-[4.75rem] !rounded-full !px-3" /> : null}
              <button
                type="button"
                onClick={onOpen}
                className="type-action inline-flex h-7 min-w-[4.75rem] shrink-0 items-center justify-center rounded-full bg-paper px-phi-3 text-[10px] text-oxford transition-[background-color,transform] duration-150 hover:bg-paper-bright active:scale-[0.98] btn-interaction focus:outline-none focus-visible:ring-2 focus-visible:ring-paper/70 motion-reduce:transition-none motion-reduce:active:scale-100"
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
