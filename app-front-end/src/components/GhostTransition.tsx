import { motion } from 'framer-motion';
import { ReactNode } from 'react';
import { tokens } from '../design-system/tokens';
import { transitionOrReduced } from '../design-system/motion';
import { usePrefersReducedMotion } from '../hooks';

interface GhostTransitionProps {
  children: ReactNode;
  className?: string;
  delay?: number;
  /** Opacity only — avoids `transform` on this wrapper so `position: sticky` descendants work in a scroll parent. */
  disableLift?: boolean;
}

/**
 * GhostTransition — fluid fade + slight lift on mount and unmount so list changes feel continuous.
 */
export default function GhostTransition({
  children,
  className = '',
  delay = 0,
  disableLift = false,
}: GhostTransitionProps) {
  const reduceMotion = usePrefersReducedMotion();
  const lift = !disableLift && !reduceMotion;
  return (
    <motion.div
      initial={lift ? { opacity: 0, y: 6 } : { opacity: 0 }}
      animate={lift ? { opacity: 1, y: 0 } : { opacity: 1 }}
      exit={lift ? { opacity: 0, y: -4 } : { opacity: 0 }}
      transition={transitionOrReduced(reduceMotion, {
        duration: tokens.motion.duration.short,
        ease: tokens.motion.ease,
        delay: reduceMotion ? 0 : delay,
      })}
      className={className}
    >
      {children}
    </motion.div>
  );
}
