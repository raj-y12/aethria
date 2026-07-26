import { motion } from 'framer-motion';
import { usePrefersReducedMotion } from '../hooks';
import { SETTINGS_GROUPS, SETTINGS_SECTIONS, type SectionId } from './settingsModel';

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
  actionLabel,
  activeSection,
  attentionSection,
  onNavigate,
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
  actionLabel: string;
  activeSection?: SectionId;
  attentionSection?: SectionId | null;
  onNavigate?: (id: SectionId) => void;
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
      className="flex-none border-b border-oxford/[0.16] bg-paper"
      initial={reduceMotion ? false : { opacity: 0, y: -8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4, ease: EASE, delay: 0.04 }}
    >
      <div className="flex flex-wrap items-center gap-x-phi-4 gap-y-phi-2 px-phi-4 py-phi-3">
        <div className="flex min-w-0 items-center gap-phi-4">
          <button
            type="button"
            onClick={onBack}
            className="type-action inline-flex min-h-11 items-center gap-phi-2 text-oxford/70 transition-colors hover:text-oxford btn-interaction focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-oxford/30"
          >
            <span aria-hidden>←</span> Aethria
          </button>
          <span className="h-4 w-px bg-oxford/15" aria-hidden />
          <p className="type-label-section text-oxford">AETHRIA / SETTINGS</p>
        </div>

        {activeSection && onNavigate ? (
          <nav className="order-3 flex w-full items-center gap-phi-1 overflow-x-auto lg:order-none lg:flex-1 lg:justify-center" aria-label="Settings areas">
            {SETTINGS_GROUPS.map((group) => {
              const sections = SETTINGS_SECTIONS.filter((section) => section.group === group.id);
              const active = sections.some((section) => section.id === activeSection);
              const needsAttention = sections.some((section) => section.id === attentionSection);
              return (
                <button
                  key={group.id}
                  type="button"
                  onClick={() => onNavigate(sections[0].id)}
                  aria-current={active ? 'page' : undefined}
                  aria-label={needsAttention ? `${group.label} — Needs attention` : group.label}
                  className={`relative flex min-h-9 shrink-0 items-center px-phi-3 py-phi-1 type-label-section transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-oxford/25 ${
                    active ? 'text-oxford' : 'text-oxford/55 hover:text-oxford/80'
                  }`}
                >
                  {active ? <span className="absolute inset-x-phi-3 bottom-0 h-px bg-oxford" aria-hidden /> : null}
                  {group.label}
                </button>
              );
            })}
          </nav>
        ) : null}

        <div className="ml-auto flex min-w-0 flex-wrap items-center justify-end gap-x-phi-4 gap-y-phi-1">
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
                  className="type-action inline-flex min-h-11 shrink-0 items-center border-b border-oxford/15 text-oxford transition-colors hover:border-oxford/50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-oxford/30"
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
            className="type-action inline-flex min-h-11 shrink-0 items-center px-phi-1 text-oxford/70 transition-colors hover:text-oxford disabled:cursor-not-allowed disabled:opacity-40 btn-interaction focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-oxford/30"
          >
            Restore defaults
          </button>
          <button
            type="button"
            onClick={onDeploy}
            disabled={saving || live}
            className="btn-aethria-solid shrink-0 disabled:cursor-not-allowed disabled:opacity-40"
          >
            {actionLabel}
          </button>
        </div>
      </div>
    </motion.header>
  );
}
