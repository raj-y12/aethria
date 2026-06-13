import { motion } from 'framer-motion';

const EASE = [0.16, 1, 0.3, 1] as const;

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
  return (
    <motion.div
      initial={{ opacity: 0, y }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5, ease: EASE, delay }}
      className={className}
    >
      {children}
    </motion.div>
  );
}
