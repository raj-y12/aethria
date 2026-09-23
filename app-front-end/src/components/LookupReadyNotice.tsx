import { motion, AnimatePresence } from 'framer-motion';
import { usePrefersReducedMotion } from '../hooks';
import { tokens } from '../design-system/tokens';

const EASE = tokens.motion.ease;

export interface LookupReadyNoticeProps {
  /** Company name when a background lookup has finished and is unopened. */
  name: string | null;
  recommendation?: 'INVEST' | 'PASS' | 'MONITOR' | null;
  recommendationLabel?: string | null;
  onOpen: () => void;
  placement?: 'inline' | 'dispatch';
  className?: string;
}

/** Completion notice for a background Dispatch lookup. Desktop places it beside Dispatch. */
export default function LookupReadyNotice({
  name,
  recommendation,
  recommendationLabel,
  onOpen,
  placement = 'inline',
  className = '',
}: LookupReadyNoticeProps) {
  const reduceMotion = usePrefersReducedMotion();
  const isDispatchPlacement = placement === 'dispatch';

  return (
    <AnimatePresence initial={false}>
      {name ? (
        <motion.div
          key="lookup-ready"
          initial={reduceMotion ? { opacity: 0 } : isDispatchPlacement ? { opacity: 0, x: -8 } : { opacity: 0, height: 0, y: -8 }}
          animate={isDispatchPlacement ? { opacity: 1, x: 0 } : { opacity: 1, height: 'auto', y: 0 }}
          exit={reduceMotion ? { opacity: 0 } : isDispatchPlacement ? { opacity: 0, x: -8 } : { opacity: 0, height: 0, y: -8 }}
          transition={{ duration: reduceMotion ? 0.12 : 0.28, ease: EASE }}
          className={`lookup-ready-notice relative z-10 w-full overflow-hidden bg-transparent px-phi-4 py-phi-2 sm:px-phi-5 ${isDispatchPlacement ? 'lookup-ready-notice--dispatch' : ''} ${className}`}
          role="status"
          aria-live="polite"
        >
          <button
            type="button"
            onClick={onOpen}
            aria-label={`Open memo for ${name}${recommendationLabel ? `, ${recommendationLabel}` : ''}`}
            className="lookup-ready-notice__plate mx-auto flex w-full max-w-[1200px] items-center gap-phi-3 rounded-full border border-oxford/30 bg-paper px-phi-4 py-phi-2 text-left transition-colors hover:border-oxford/60 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-oxford/35 sm:px-phi-5"
          >
            <span className="min-w-0 flex-1">
              <span className="block font-mono text-[9px] font-medium uppercase leading-tight tracking-[0.12em] text-oxford/60">Dispatch complete</span>
              <span className="mt-0.5 block truncate font-sans text-[12px] font-semibold leading-tight tracking-[-0.01em] text-oxford">{name}</span>
            </span>
            {recommendation ? (
              <span className="shrink-0 rounded-full bg-oxford px-phi-3 py-phi-1 font-mono text-[9px] font-medium uppercase leading-tight tracking-[0.08em] text-paper">
                {recommendationLabel ?? recommendation}
              </span>
            ) : null}
          </button>
        </motion.div>
      ) : null}
    </AnimatePresence>
  );
}
