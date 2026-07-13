import { motion } from 'framer-motion';
import type { Settings } from '../api/settings';
import { usePrefersReducedMotion } from '../hooks';
import OperationsStrip from './OperationsStrip';
import { SETTINGS_SECTIONS, type SectionId } from './settingsModel';

const EASE = [0.16, 1, 0.3, 1] as const;
const INDICATOR_EASE = [0.77, 0, 0.175, 1] as const;

const GROUPS: Array<{ title: string; tag: string; tab: 'decision' | 'admin' }> = [
  { title: 'Configuration', tag: 'Deploys', tab: 'decision' },
  { title: 'Administration', tag: 'Live', tab: 'admin' },
];

/**
 * The focused-mode navigation rail — stands where the app spine used to be.
 * A scroll-spy table of contents (clicking scrolls; the active item is driven
 * by what's on screen) with the instant-save pipeline controls pinned at its
 * foot. The active marker slides between items via a shared layout animation.
 */
export default function SettingsRail({
  activeSection,
  onNavigate,
  settings,
  storageUnavailable,
  onSettingsChange,
}: {
  activeSection: SectionId;
  onNavigate: (id: SectionId) => void;
  settings: Settings;
  storageUnavailable: boolean;
  onSettingsChange: (settings: Settings) => void;
}) {
  const reduceMotion = usePrefersReducedMotion();
  return (
    <motion.aside
      className="hidden w-[13.5rem] flex-none flex-col overflow-y-auto border-r border-oxford/[0.08] bg-paper lg:flex"
      aria-label="Settings sections"
      initial={reduceMotion ? false : { opacity: 0, x: -10 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ duration: 0.45, ease: EASE, delay: 0.1 }}
    >
      <nav className="flex flex-col gap-phi-5 px-phi-4 py-phi-6">
        {GROUPS.map((group) => (
          <div key={group.title}>
            <div className="flex items-baseline justify-between gap-phi-2 px-phi-2 pb-phi-2">
              <p className="type-label-section">{group.title}</p>
              <span className="type-status text-oxford/40">{group.tag}</span>
            </div>
            <div className="flex flex-col">
              {SETTINGS_SECTIONS.filter((section) => section.tab === group.tab).map((section) => {
                const active = activeSection === section.id;
                return (
                  <button
                    key={section.id}
                    type="button"
                    onClick={() => onNavigate(section.id)}
                    aria-current={active ? 'true' : undefined}
                    className={`relative flex items-center px-phi-2 py-phi-2 text-left type-body-sm transition-colors btn-interaction btn-interaction--no-press focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-oxford/30 ${
                      active ? 'text-oxford' : 'text-oxford/55 hover:text-oxford/80'
                    }`}
                  >
                    {active ? (
                      <motion.span
                        layoutId="settings-rail-active"
                        className="absolute inset-y-1 left-0 w-[2px] bg-oxford"
                        transition={reduceMotion ? { duration: 0 } : { duration: 0.28, ease: INDICATOR_EASE }}
                        aria-hidden
                      />
                    ) : null}
                    <span className="truncate">{section.label}</span>
                  </button>
                );
              })}
            </div>
          </div>
        ))}
      </nav>

      <div className="mt-auto border-t border-oxford/[0.08]">
        <OperationsStrip
          variant="rail"
          settings={settings}
          storageUnavailable={storageUnavailable}
          onSettingsChange={onSettingsChange}
        />
      </div>
    </motion.aside>
  );
}
