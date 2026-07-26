import { motion } from 'framer-motion';
import { usePrefersReducedMotion } from '../hooks';
import { SETTINGS_GROUPS, SETTINGS_SECTIONS, type SectionId } from './settingsModel';

const EASE = [0.16, 1, 0.3, 1] as const;
const INDICATOR_EASE = [0.77, 0, 0.175, 1] as const;

/**
 * Compact settings area navigation. The room uses a horizontal group bar;
 * the reading column remains the source of truth for individual sections.
 */
export default function SettingsRail({
  activeSection,
  attentionSection,
  onNavigate,
}: {
  activeSection: SectionId;
  attentionSection: SectionId | null;
  onNavigate: (id: SectionId) => void;
}) {
  const reduceMotion = usePrefersReducedMotion();
  return (
    <motion.div
      className="hidden flex-none border-b border-oxford/[0.10] bg-paper lg:block"
      aria-label="Settings areas"
      initial={reduceMotion ? false : { opacity: 0, x: -10 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ duration: 0.45, ease: EASE, delay: 0.1 }}
    >
      <nav className="mx-auto flex max-w-[860px] items-center gap-phi-1 overflow-x-auto px-phi-5 py-phi-2" aria-label="Settings areas">
        {SETTINGS_GROUPS.map((group) => (
          (() => {
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
                {active ? (
                  <motion.span
                    layoutId="settings-rail-active"
                    className="absolute inset-x-phi-3 bottom-0 h-px bg-oxford"
                    transition={reduceMotion ? { duration: 0 } : { duration: 0.28, ease: INDICATOR_EASE }}
                    aria-hidden
                  />
                ) : null}
                {group.label}
              </button>
            );
          })()
        ))}
      </nav>
    </motion.div>
  );
}
