import { useRef } from 'react';
import { motion } from 'framer-motion';
import { tokens } from '../design-system/tokens';
import { usePrefersReducedMotion } from '../hooks';

/**
 * A segmented pill switch: the active option is a filled oxford capsule that
 * slides between options inside a hairline-bordered track (the same control as
 * Settings' compact segments, `.compact-seg`; the border lives in index.css). Used for page-level
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
  /** `count` sits after the label; `tone: 'new'` adds a breathing dot to an
   *  inactive option. `'escalation'` is accepted but no longer tints the text —
   *  the switch keeps the Settings segment's single oxford palette. */
  options: readonly { key: T; label: string; count?: string; tone?: 'escalation' | 'new' }[];
  value: T;
  onChange: (key: T) => void;
  label: string;
  layoutId: string;
  className?: string;
}) {
  const reduceMotion = usePrefersReducedMotion();
  const buttonsRef = useRef<Array<HTMLButtonElement | null>>([]);

  // The tabs pattern the roles announce: arrows / Home / End move and select,
  // and only the active option sits in the Tab order (roving tabindex).
  const onKeyDown = (event: React.KeyboardEvent) => {
    const current = options.findIndex((option) => option.key === value);
    const last = options.length - 1;
    const next =
      event.key === 'ArrowRight' ? (current >= last ? 0 : current + 1)
      : event.key === 'ArrowLeft' ? (current <= 0 ? last : current - 1)
      : event.key === 'Home' ? 0
      : event.key === 'End' ? last
      : null;
    if (next == null) return;
    event.preventDefault();
    onChange(options[next].key);
    buttonsRef.current[next]?.focus();
  };

  return (
    <nav
      role="tablist"
      aria-label={label}
      onKeyDown={onKeyDown}
      className={`segmented-pill inline-flex items-center rounded-full p-[2px] overflow-x-auto no-scrollbar ${className}`.trim()}
    >
      {options.map((option, index) => {
        const isActive = value === option.key;
        return (
          <button
            key={option.key}
            ref={(el) => { buttonsRef.current[index] = el; }}
            type="button"
            role="tab"
            aria-selected={isActive}
            tabIndex={isActive ? 0 : -1}
            onClick={() => onChange(option.key)}
            // Colour and type match Settings' .compact-seg (12px sans),
            // oxford at 70% idle, full oxford on hover, paper on the capsule.
            className={`group relative min-h-[26px] shrink-0 rounded-full px-3 font-sans text-[12px] font-medium cursor-pointer btn-interaction btn-interaction--no-press transition-colors duration-300 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-oxford/35 ${
              isActive ? 'text-paper' : 'text-oxford/70 hover:text-oxford'
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
            <span className="relative inline-flex items-center gap-phi-2 whitespace-nowrap">
              {option.tone === 'new' && !isActive ? (
                <span aria-hidden className="h-[6px] w-[6px] rounded-full bg-oxford signal-dot-breathe" />
              ) : null}
              {option.label}
              {option.count != null ? <span className="tabular-nums opacity-70">{option.count}</span> : null}
            </span>
          </button>
        );
      })}
    </nav>
  );
}
