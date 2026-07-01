import { motion, useReducedMotion } from 'framer-motion';
import { SCROLL_EASE } from '../motionTokens';

/**
 * The portfolio layer — what happens after INVEST. Real facts from backend/portfolio/:
 * tracks accepted companies across execution, signals, feedback, and health checks.
 */
const TRACKS = ['Execution', 'Signals', 'Feedback', 'Health checks'] as const;

export default function PortfolioSection() {
  const reduce = useReducedMotion();

  return (
    <section
      id="portfolio"
      className="w-full border-t border-solid border-[var(--section-divider)]"
      style={{ backgroundColor: 'var(--color-paper)' }}
      aria-labelledby="portfolio-heading"
    >
      <div className="page-margin-x py-[clamp(6rem,16vh,12rem)]">
        <p className="font-mono text-[11px] uppercase tracking-[0.16em] text-[var(--color-accent)]">A8 — The Portfolio</p>

        <motion.div
          initial={reduce ? false : { opacity: 0, y: 18 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, amount: 0.35 }}
          transition={{ duration: reduce ? 0 : 0.7, ease: SCROLL_EASE }}
        >
          <h2
            id="portfolio-heading"
            className="editorial-display mt-6 max-w-[22ch] font-normal text-[clamp(2rem,4.6vw,3.4rem)] leading-[1.02] tracking-[-0.02em] text-[var(--color-oxford)]"
          >
            The record doesn't end at <span className="italic text-[var(--color-accent)]">invest</span>.
          </h2>
          <p className="mt-5 max-w-[58ch] font-sans text-[15px] leading-[1.7] text-[var(--text-secondary)]">
            Every company the partner engine accepts moves into a portfolio layer that keeps watching — the same
            evidence discipline applied to the decision, now applied to what happens after it.
          </p>
        </motion.div>

        <motion.div
          className="mt-10 flex flex-wrap gap-x-10 gap-y-4 border-t border-solid border-[var(--section-divider)] pt-8"
          initial={reduce ? false : { opacity: 0 }}
          whileInView={{ opacity: 1 }}
          viewport={{ once: true, amount: 0.4 }}
          transition={{ duration: reduce ? 0 : 0.6, delay: reduce ? 0 : 0.15 }}
        >
          {TRACKS.map((t, i) => (
            <span key={t} className="flex items-baseline gap-2 font-mono text-[11px] uppercase tracking-[0.1em] text-[var(--label-muted)]">
              <span className="text-[var(--color-accent)]">{String(i + 1).padStart(2, '0')}</span>
              {t}
            </span>
          ))}
        </motion.div>
      </div>
    </section>
  );
}
