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
          className="pointer-events-none fixed bottom-phi-5 right-phi-5 z-[9998] flex justify-end px-phi-0 max-sm:inset-x-phi-3 max-sm:right-auto"
          role="status"
          aria-live="polite"
        >
          <div className="pointer-events-auto flex w-full max-w-[min(92vw,24rem)] items-center gap-phi-3 border border-oxford/20 bg-paper-bright px-phi-3 py-phi-3 text-oxford shadow-[0_10px_28px_rgba(0,20,51,0.12)]">
            <span className="flex h-7 w-7 shrink-0 items-center justify-center bg-oxford font-mono text-[12px] text-paper" aria-hidden>✓</span>
            <div className="min-w-0 flex-1">
              <div className="type-status text-oxford/55">Memo ready</div>
              <p className="mt-phi-1 truncate font-sans text-[15px] font-medium leading-tight text-oxford">{name}</p>
            </div>
            <div className="flex shrink-0 items-center gap-phi-2">
              {recommendation ? <DecisionBadge variant={recommendation} /> : null}
              <button
                type="button"
                onClick={onOpen}
                className="type-action inline-flex h-[32px] shrink-0 items-center justify-center bg-oxford px-phi-3 text-paper transition-[background-color,transform] duration-150 hover:bg-oxford/90 active:scale-[0.98] btn-interaction focus:outline-none focus-visible:ring-2 focus-visible:ring-oxford/45 motion-reduce:transition-none motion-reduce:active:scale-100"
              >
                Open memo
              </button>
              <button type="button" onClick={onDismiss} aria-label="Dismiss memo ready notification" className="shrink-0 cursor-pointer border-0 bg-transparent p-1 text-base leading-none text-oxford/45 transition-colors hover:text-oxford btn-interaction focus:outline-none focus-visible:ring-2 focus-visible:ring-oxford/45">×</button>
            </div>
          </div>
        </motion.div>
      ) : null}
    </AnimatePresence>
  );

  if (typeof document === 'undefined') return null;
  return createPortal(toast, document.body);
}
