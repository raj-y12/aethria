import { motion } from 'framer-motion';
import { usePrefersReducedMotion } from '../hooks';
import { transitionOrReduced } from '../design-system/motion';
import { tokens } from '../design-system/tokens';

const EASE = tokens.motion.ease;

/**
 * The house entrance motion — the Dispatch takeover's staggered upward
 * reveal, shared by the front door and every room header.
 */
export default function Reveal({
  delay,
  y = 10,
  className,
  children,
}: {
  delay: number;
  y?: number;
  className?: string;
  children: React.ReactNode;
}) {
  const reduceMotion = usePrefersReducedMotion();
  return (
    <motion.div
      // `initial={false}` starts at the settled state, so reduced motion skips
      // the travel outright rather than playing it at zero duration.
      initial={reduceMotion ? false : { opacity: 0, y }}
      animate={{ opacity: 1, y: 0 }}
      transition={transitionOrReduced(reduceMotion, { duration: 0.5, ease: EASE, delay })}
      className={className}
    >
      {children}
    </motion.div>
  );
}
