import { motion, useReducedMotion, type HTMLMotionProps } from 'framer-motion';
import type { CSSProperties, ReactNode } from 'react';
import { scrollRevealTransition } from '../motionTokens';

type ScrollRevealProps = {
  children: ReactNode;
  className?: string;
  delay?: number;
  y?: number;
  once?: boolean;
  amount?: number | 'some' | 'all';
  style?: CSSProperties;
} & Omit<HTMLMotionProps<'div'>, 'children' | 'initial' | 'animate' | 'style'>;

/**
 * Scroll animation wrapper.
 *
 * Content stays visible by default; motion is an enhancement only. This avoids blank sections in
 * full-page captures, background tabs, and any browser state where IntersectionObserver is delayed.
 */
export function ScrollReveal({
  children,
  className,
  delay = 0,
  y = 20,
  once = true,
  amount = 0.15,
  style,
  ...rest
}: ScrollRevealProps) {
  const reduce = useReducedMotion();
  return (
    <motion.div
      className={className}
      style={style}
      initial={false}
      whileInView={reduce ? undefined : { opacity: 1, y: 0 }}
      viewport={{ once, amount, margin: '0px 0px -6% 0px' }}
      transition={scrollRevealTransition(reduce ? 0 : 0.55, reduce ? 0 : delay)}
      {...rest}
    >
      {children}
    </motion.div>
  );
}
