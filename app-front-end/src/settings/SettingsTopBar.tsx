import { motion } from 'framer-motion';
import { usePrefersReducedMotion } from '../hooks';

const EASE = [0.16, 1, 0.3, 1] as const;

/**
 * The focused-mode top edge. Left: an exit back to the app (the spine is gone
 * in this mode, so this is the only way out). Right: live deploy state and the
 * one deploy transaction. Runtime toggles live in the rail, not here.
 */
export default function SettingsTopBar({
  live,
  pendingCount,
  saving,
  onBack,
  onReset,
  onDeploy,
}: {
  live: boolean;
  pendingCount: number;
  saving: boolean;
  onBack: () => void;
  onReset: () => void;
  onDeploy: () => void;
}) {
  const reduceMotion = usePrefersReducedMotion();
  return (
    <motion.header
      className="flex-none border-b border-oxford/[0.08] bg-paper"
      initial={reduceMotion ? false : { opacity: 0, y: -8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4, ease: EASE, delay: 0.04 }}
    >
      <div className="flex items-center justify-between gap-phi-4 px-phi-5 py-phi-3 lg:px-phi-6">
        <div className="flex min-w-0 items-center gap-phi-4">
          <button
            type="button"
            onClick={onBack}
            className="type-action inline-flex items-center gap-phi-2 text-oxford/60 transition-colors hover:text-oxford btn-interaction focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-oxford/30"
          >
            <span aria-hidden>←</span> Aethria
          </button>
          <span className="h-4 w-px bg-oxford/15" aria-hidden />
          <p className="type-display text-[1.2rem] leading-none text-oxford">
            Settings<span className="wordmark-dot">.</span>
          </p>
        </div>

        <div className="flex items-center gap-phi-4">
          <span
            className="type-status hidden items-center gap-phi-2 sm:inline-flex"
            aria-live="polite"
          >
            <span
              className={`h-1.5 w-1.5 shrink-0 ${live ? 'bg-oxford' : 'bg-escalation/70 signal-dot-breathe'}`}
              aria-hidden
            />
            <span className={live ? 'text-oxford/60' : 'text-escalation/80'}>
              {live ? 'Live' : `Draft · ${pendingCount} pending`}
            </span>
          </span>
          <button
            type="button"
            onClick={onReset}
            disabled={saving}
            className="type-action inline-flex min-h-11 items-center px-phi-1 text-oxford/60 transition-colors hover:text-oxford disabled:cursor-not-allowed disabled:opacity-40 btn-interaction focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-oxford/30"
          >
            Reset
          </button>
          <button
            type="button"
            onClick={onDeploy}
            disabled={saving || live}
            className="btn-aethria-solid disabled:cursor-not-allowed disabled:opacity-40"
          >
            {saving ? 'Deploying…' : 'Deploy changes'}
          </button>
        </div>
      </div>
    </motion.header>
  );
}
