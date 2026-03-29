import { motion } from 'framer-motion';
import { ReactNode } from 'react';
import { tokens } from '../design-system/tokens';

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
  return (
    <motion.div
      initial={disableLift ? { opacity: 0 } : { opacity: 0, y: 6 }}
      animate={disableLift ? { opacity: 1 } : { opacity: 1, y: 0 }}
      exit={disableLift ? { opacity: 0 } : { opacity: 0, y: -4 }}
      transition={{
        duration: tokens.motion.duration.short,
        ease: tokens.motion.ease,
        delay,
      }}
      className={className}
    >
      {children}
    </motion.div>
  );
}
