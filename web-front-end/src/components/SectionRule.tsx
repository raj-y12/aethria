import { motion, useReducedMotion } from 'framer-motion';
import { SCROLL_EASE } from '../motionTokens';

interface SectionRuleProps {
  /** 2px oxford bar instead of a hairline — a major boundary. */
  heavy?: boolean;
  /** Paper rule for use on dark (oxford) sections. */
  inverse?: boolean;
}

/**
 * A section boundary that draws itself in from the left as it enters view — the
 * page's signature entrance, in place of the fade-up-everything reveal. Full-bleed,
 * so it replaces the static border-t on section elements.
 */
export default function SectionRule({ heavy = false, inverse = false }: SectionRuleProps) {
  const reduce = useReducedMotion();
  const background = inverse
    ? heavy
      ? 'rgba(244,241,234,0.9)'
      : 'rgba(244,241,234,0.22)'
    : heavy
      ? 'var(--color-oxford)'
      : 'var(--section-divider)';

  return (
    <motion.div
      aria-hidden
      className="w-full origin-left"
      style={{ height: heavy ? 2 : 1, backgroundColor: background }}
      initial={reduce ? false : { scaleX: 0 }}
      whileInView={{ scaleX: 1 }}
      viewport={{ once: true, amount: 0.6 }}
      transition={{ duration: reduce ? 0 : 0.75, ease: SCROLL_EASE }}
    />
  );
}
