import { motion } from 'framer-motion';
import { ReactNode } from 'react';
import { tokens } from '../design-system/tokens';

interface GhostTransitionProps {
  children: ReactNode;
  className?: string;
  delay?: number;
}

/**
 * GhostTransition — matches Enter System page smoothness.
 */
export default function GhostTransition({ 
  children, 
  className = '',
  delay = 0 
}: GhostTransitionProps) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -12 }}
      transition={{ duration: tokens.motion.duration.medium, ease: tokens.motion.ease, delay }}
      className={className}
    >
      {children}
    </motion.div>
  );
}
