import { motion } from 'framer-motion';
import { tokens } from '../design-system/tokens';
import { usePrefersReducedMotion } from '../hooks';

/**
 * A segmented pill switch: the active option is a filled oxford capsule that
 * slides between options on a whisper-of-oxford track. Used for page-level
 * views (Fund facets, Portfolio Held/Decided). `layoutId` must be unique per
 * switch on screen so the capsules don't animate into each other.
 */
export default function SegmentedPill<T extends string>({
  options,
  value,
  onChange,
  label,
  layoutId,
  className = '',
}: {
  options: readonly { key: T; label: string }[];
  value: T;
  onChange: (key: T) => void;
  label: string;
  layoutId: string;
  className?: string;
}) {
  const reduceMotion = usePrefersReducedMotion();

  return (
    <nav
      role="tablist"
      aria-label={label}
      className={`segmented-pill inline-flex items-center rounded-full bg-oxford/[0.06] p-[3px] overflow-x-auto no-scrollbar ${className}`.trim()}
    >
      {options.map((option) => {
        const isActive = value === option.key;
        return (
          <button
            key={option.key}
            type="button"
            role="tab"
            aria-selected={isActive}
            onClick={() => onChange(option.key)}
            className={`type-action group relative min-h-[30px] shrink-0 rounded-full px-phi-4 cursor-pointer btn-interaction btn-interaction--no-press transition-colors duration-300 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-oxford/35 ${
              isActive ? 'text-paper' : 'text-oxford/55 hover:text-oxford'
            }`}
            style={{ transitionTimingFunction: 'var(--motion-ease)' }}
          >
            {isActive ? (
              <motion.span
                layoutId={layoutId}
                className="absolute inset-0 rounded-full bg-oxford"
                transition={reduceMotion ? { duration: 0 } : { duration: 0.3, ease: tokens.motion.easeInOut }}
                aria-hidden
              />
            ) : null}
            <span className="relative">{option.label}</span>
          </button>
        );
      })}
    </nav>
  );
}
