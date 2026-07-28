import { motion } from 'framer-motion';
import { usePrefersReducedMotion } from '../hooks';
import { SETTINGS_GROUPS, SETTINGS_SECTIONS, type SectionId } from './settingsModel';
import { SpineNavButton } from '../components/SystemBar';

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
      /* The paper twin of AppSpine: same width (--spine-width) and the same lg
         breakpoint the oxford spine uses, so the rail appears and disappears in
         step with it. At md it turned on 256px earlier than the main nav, which
         left Settings with a side rail on viewports where nothing else had one. */
      className="flex-none border-b border-oxford/[0.16] bg-paper lg:fixed lg:inset-y-0 lg:left-0 lg:z-40 lg:flex lg:w-[var(--spine-width)] lg:flex-col lg:justify-between lg:border-b-0"
      initial={reduceMotion ? false : { opacity: 0, y: -8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4, ease: EASE, delay: 0.04 }}
    >
      <div className="flex flex-wrap items-center gap-x-phi-4 gap-y-phi-2 px-phi-4 py-phi-3 lg:h-full lg:min-h-0 lg:flex-col lg:items-stretch lg:gap-phi-4 lg:px-phi-4 lg:pb-phi-4 lg:pt-phi-5">
        <div className="flex min-w-0 items-center gap-phi-4 lg:block lg:shrink-0 lg:px-2">
          <button
            type="button"
            onClick={onBack}
            className="type-action inline-flex min-h-11 items-center gap-phi-2 text-oxford/70 transition-colors hover:text-oxford btn-interaction focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-oxford/30"
          >
            <span aria-hidden>←</span> Aethria
          </button>
        </div>

        {activeSection && onNavigate ? (
          <nav className="order-3 flex w-full items-center gap-phi-1 overflow-x-auto lg:order-none lg:flex-col lg:items-stretch lg:gap-0.5 lg:overflow-y-auto" aria-label="Settings areas">
            {SETTINGS_GROUPS.map((group, index) => {
              const sections = SETTINGS_SECTIONS.filter((section) => section.group === group.id);
              const active = sections.some((section) => section.id === activeSection);
              const needsAttention = sections.some((section) => section.id === attentionSection);
              return (
                <SpineNavButton
                  key={group.id}
                  label={needsAttention ? `${group.label} — Needs attention` : group.label}
                  active={active}
                  ariaPressed={active}
                  onClick={() => onNavigate(sections[0].id)}
                  shortcut={String(index + 1)}
                  compact
                  surface="paper"
                  indicatorId="settings-areas-active"
                />
              );
            })}
          </nav>
        ) : null}

        <div className="ml-auto flex min-w-0 flex-wrap items-center justify-end gap-x-phi-4 gap-y-phi-1 lg:mt-auto lg:ml-0 lg:w-full lg:flex-col lg:items-stretch lg:gap-3 lg:px-2">
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
