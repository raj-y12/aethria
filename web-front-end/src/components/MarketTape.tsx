import { motion, useReducedMotion } from 'framer-motion';
import { SCROLL_EASE } from '../motionTokens';

/**
 * Hero ticker — Space Mono 9px, Oxford @ 40% on paper. Seamless linear marquee.
 */
const SEGMENTS = [
  'SOURCE TRAIL RETAINED',
  'REVIEWER DISAGREEMENT VISIBLE',
  'MANDATE FIT RECORDED',
  'POLICY-BACKED RECOMMENDATION',
  'INVESTMENT RECORD PREPARED',
];

const LINE = SEGMENTS.join(' · ');

export default function MarketTape() {
  const reduce = useReducedMotion();
  return (
    <motion.div
      className="market-tape market-tape-shell overflow-hidden bg-[var(--color-paper)]"
      aria-hidden
      initial={reduce ? false : { opacity: 0, y: 10 }}
      whileInView={reduce ? undefined : { opacity: 1, y: 0 }}
      viewport={{ once: true, amount: 0.35 }}
      transition={{ duration: reduce ? 0 : 0.5, ease: SCROLL_EASE }}
    >
      <div className="market-tape-marquee flex w-max items-center font-mono text-[9px] tracking-[0.12em] uppercase text-[rgba(0,27,71,0.4)] py-3">
        <span className="shrink-0 pr-20">{LINE}</span>
        <span className="shrink-0 pr-20">{LINE}</span>
      </div>
    </motion.div>
  );
}
