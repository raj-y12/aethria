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
          <div className="pointer-events-auto flex w-full max-w-[min(92vw,30rem)] flex-wrap items-center gap-x-phi-3 gap-y-phi-2 rounded-lg bg-oxford px-phi-3 py-phi-2.5 text-paper shadow-[0_12px_36px_rgba(0,20,51,0.18)] sm:flex-nowrap sm:px-phi-4">
            <div className="flex min-w-0 flex-1 items-baseline gap-phi-2">
              <div className="flex shrink-0 items-center gap-phi-2 type-status text-paper/65">
                <span className="h-1.5 w-1.5 shrink-0 bg-paper signal-dot-breathe" aria-hidden />
                <span>Memo ready</span>
              </div>
              <p className="min-w-0 truncate font-display text-[1.05rem] leading-tight text-paper">{name}</p>
            </div>
            <div className="ml-auto flex items-center gap-phi-2">
              {recommendation ? <DecisionBadge variant={recommendation} className="!rounded-md" /> : null}
              <button
                type="button"
                onClick={onOpen}
                className="type-action inline-flex h-[30px] shrink-0 items-center justify-center rounded-md bg-paper px-phi-3 text-oxford transition-[background-color,transform] duration-150 hover:bg-paper-bright active:scale-[0.98] btn-interaction focus:outline-none focus-visible:ring-2 focus-visible:ring-paper/70 motion-reduce:transition-none motion-reduce:active:scale-100"
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
