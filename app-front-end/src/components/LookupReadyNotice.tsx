import { motion, AnimatePresence } from 'framer-motion';
import DecisionBadge from './DecisionBadge';
import { usePrefersReducedMotion } from '../hooks';
import { tokens } from '../design-system/tokens';

const EASE = tokens.motion.ease;

interface LookupReadyNoticeProps {
  /** Company name when a background lookup has finished and is unopened. */
  name: string | null;
  recommendation?: 'INVEST' | 'PASS' | 'MONITOR' | null;
  recommendationLabel?: string | null;
  onOpen: () => void;
  onDismiss: () => void;
}

/**
 * Inline completion handoff for a background Dispatch lookup.
 * It belongs to the workspace flow rather than floating above it like a toast.
 */
export default function LookupReadyNotice({ name, recommendation, recommendationLabel, onOpen, onDismiss }: LookupReadyNoticeProps) {
  const reduceMotion = usePrefersReducedMotion();

  return (
    <AnimatePresence initial={false}>
      {name ? (
        <motion.div
          key="lookup-ready"
          initial={reduceMotion ? { opacity: 0 } : { opacity: 0, height: 0 }}
          animate={{ opacity: 1, height: 'auto' }}
          exit={reduceMotion ? { opacity: 0 } : { opacity: 0, height: 0 }}
          transition={{ duration: reduceMotion ? 0.12 : 0.28, ease: EASE }}
          className="relative z-10 w-full overflow-hidden border-y border-oxford/[0.12] bg-paper"
          role="status"
          aria-live="polite"
        >
          <div className="mx-auto flex w-full max-w-[1200px] items-center gap-phi-3 px-phi-5 py-phi-3 sm:px-phi-7">
            <span className="h-1.5 w-1.5 shrink-0 bg-oxford signal-dot-breathe" aria-hidden />
            <div className="min-w-0 flex-1">
              <p className="type-label-section">Dispatch complete</p>
              <p className="mt-phi-1 truncate font-display text-[15px] leading-tight text-oxford">
                <span className="sr-only">Memo ready: </span>
                {name}
              </p>
            </div>
            {recommendation ? <DecisionBadge variant={recommendationLabel === 'More diligence' ? 'escalation' : recommendation} label={recommendationLabel?.toUpperCase()} /> : null}
            <button
              type="button"
              onClick={onOpen}
              className="type-action shrink-0 border-b border-oxford/25 pb-0.5 text-oxford transition-colors hover:border-oxford hover:text-oxford btn-interaction focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-oxford/35"
            >
              Open memo →
            </button>
            <button
              type="button"
              onClick={onDismiss}
              aria-label="Dismiss memo ready notification"
              className="type-action shrink-0 border-0 bg-transparent p-1 text-oxford/65 transition-colors hover:text-oxford btn-interaction focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-oxford/35"
            >
              Dismiss
            </button>
          </div>
        </motion.div>
      ) : null}
    </AnimatePresence>
  );
}
