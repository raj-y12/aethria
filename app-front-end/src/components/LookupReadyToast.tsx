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
        <motion.div
          key="lookup-ready"
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: 16 }}
          transition={{ duration: 0.28, ease: EASE }}
          className="fixed bottom-phi-5 left-1/2 z-[9998] flex -translate-x-1/2 items-center gap-phi-4 border border-oxford/15 bg-paper px-phi-4 py-phi-3 shadow-[0_18px_44px_-18px_rgba(0,20,51,0.35)]"
          role="status"
          aria-live="polite"
        >
          <span className="h-1.5 w-1.5 shrink-0 rounded-none bg-oxford signal-dot-breathe" aria-hidden />
          <span className="min-w-0">
            <span className="block font-mono text-[10px] uppercase tracking-[0.14em] text-oxford/40">
              Lookup ready{recommendation ? ` · ${recommendation}` : ''}
            </span>
            <span className="block truncate type-body-sm font-medium text-oxford">{name}</span>
          </span>
          <button
            type="button"
            onClick={onOpen}
            className="shrink-0 type-meta uppercase tracking-[0.12em] bg-oxford px-phi-3 py-phi-2 text-paper transition-opacity hover:opacity-90 btn-interaction focus:outline-none focus-visible:ring-2 focus-visible:ring-oxford/35"
          >
            Open memo
          </button>
          <button
            type="button"
            onClick={onDismiss}
            aria-label="Dismiss"
            className="shrink-0 type-meta text-oxford/30 hover:text-oxford/60 bg-transparent border-0 p-0 cursor-pointer transition-colors btn-interaction"
          >
            ×
          </button>
        </motion.div>
      ) : null}
    </AnimatePresence>
  );

  if (typeof document === 'undefined') return null;
  return createPortal(toast, document.body);
}
