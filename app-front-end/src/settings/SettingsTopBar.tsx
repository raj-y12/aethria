import { motion } from 'framer-motion';
import { usePrefersReducedMotion } from '../hooks';

const EASE = [0.16, 1, 0.3, 1] as const;

export type SettingsStatusTone = 'live' | 'draft' | 'progress' | 'error' | 'restored' | 'success';

/** Fixed settings action point. Transaction state is owned by SettingsPage. */
export default function SettingsTopBar({
  live,
  saving,
  message,
  tone,
  canUndo,
  onBack,
  onRestoreDefaults,
  onUndo,
  onDeploy,
}: {
  live: boolean;
  saving: boolean;
  message: string;
  tone: SettingsStatusTone;
  canUndo: boolean;
  onBack: () => void;
  onRestoreDefaults: () => void;
  onUndo: () => void;
  onDeploy: () => void;
}) {
  const reduceMotion = usePrefersReducedMotion();
  const statusClass = tone === 'error'
    ? 'text-escalation/85'
    : tone === 'draft' || tone === 'progress'
      ? 'text-escalation/80'
      : 'text-oxford/70';
  const statusDot = tone === 'error' || tone === 'draft' || tone === 'progress'
    ? 'bg-escalation/70'
    : 'bg-oxford';

  return (
    <motion.header
      className="flex-none border-b border-oxford/[0.08] bg-paper"
      initial={reduceMotion ? false : { opacity: 0, y: -8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4, ease: EASE, delay: 0.04 }}
    >
      <div className="flex flex-wrap items-center justify-between gap-x-phi-4 gap-y-phi-2 px-phi-5 py-phi-3 lg:px-phi-6">
        <div className="flex min-w-0 items-center gap-phi-4">
          <button
            type="button"
            onClick={onBack}
            className="type-action inline-flex min-h-11 items-center gap-phi-2 !text-xs text-oxford/70 transition-colors hover:text-oxford btn-interaction focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-oxford/30"
          >
            <span aria-hidden>←</span> Aethria
          </button>
          <span className="h-4 w-px bg-oxford/15" aria-hidden />
          <p className="type-display text-[1.2rem] leading-none text-oxford">
            Settings<span className="wordmark-dot">.</span>
          </p>
        </div>

        <div className="flex min-w-0 flex-1 flex-wrap items-center justify-end gap-x-phi-4 gap-y-phi-1">
          <span
            className={`type-status inline-flex min-w-0 items-center gap-phi-2 !text-xs ${statusClass}`}
            aria-live="polite"
            role={tone === 'error' ? 'alert' : 'status'}
          >
            <span className={`h-1.5 w-1.5 shrink-0 ${statusDot}`} aria-hidden />
            <span className="break-words">{message}</span>
            {canUndo ? (
              <>
                <span aria-hidden>·</span>
                <button
                  type="button"
                  onClick={onUndo}
                  className="type-action inline-flex min-h-11 shrink-0 items-center border-b border-oxford/15 !text-xs text-oxford transition-colors hover:border-oxford/50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-oxford/30"
                >
                  Undo
                </button>
              </>
            ) : null}
          </span>
          <button
            type="button"
            onClick={onRestoreDefaults}
            disabled={saving}
            className="type-action inline-flex min-h-11 shrink-0 items-center px-phi-1 !text-xs text-oxford/70 transition-colors hover:text-oxford disabled:cursor-not-allowed disabled:opacity-40 btn-interaction focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-oxford/30"
          >
            Restore defaults
          </button>
          <button
            type="button"
            onClick={onDeploy}
            disabled={saving || live}
            className="btn-aethria-solid min-h-11 shrink-0 text-xs disabled:cursor-not-allowed disabled:opacity-40"
          >
            {saving ? 'Deploying…' : 'Deploy changes'}
          </button>
        </div>
      </div>
    </motion.header>
  );
}
